import base64
import io
import json
import math
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import MILP_Solver
import pandas as pd

# import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

# from openpyxl import load_workbook

# 1) FastAPI app and CORS
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2) Pydantic Model for the incoming plan data
# class PlanPayload(BaseModel):
#     """
#     Updated payload structure without startYear.
#     Example payload structure:
#     {
#       "products": { ... },
#       "Min_Stock": { ... },
#       "Export_Stocks": { ... },
#       "Sales_Stocks": { ... },
#       "monthsCount": 12,
#       "commonBRs": [ ... ],
#       "dedicatedBRs": [ ... ]
#     }
#     """
#     products: Dict[str, List[str]]  # product -> list of dose strings
#     Min_Stock: Dict[str, Dict[str, Dict[int, int]]]
#     Export_Stocks: Dict[str, Dict[str, Dict[int, int]]]
#     Sales_Stocks: Dict[str, Dict[str, Dict[int, int]]]
#     monthsCount: int
#     commonBRs: List[Dict[str, Any]]
#     dedicatedBRs: List[Dict[str, Any]]
#     selectedDate: Optional[str] = None   # New field for the date


from typing import Optional, Dict, List, Any
from pydantic import BaseModel

class PlanPayload(BaseModel):
    """
    Updated payload structure without custom classes. Example payload:
    {
      "products": { ... },
      "Min_Stock": { ... },
      "Export_Stocks": { ... },
      "Sales_Stocks": { ... },
      "monthsCount": 12,
      "commonBRs": [ ... ],
      "dedicatedBRs": [ ... ],
      "selectedDate": "2025-04-11T20:30:00.000Z",
      "currentStocks": [
         {
           "productDose": "Altebrel|25",
           "amount": 4845,
           "Date": "2025-04-11T20:30:00.000Z",
           "Expiration": "28/11/2025"
         },
         {
           "productDose": "Arylia|60",
           "amount": 654,
           "Date": "2025-04-11T20:30:00.000Z",
           "Expiration": "31/08/2025"
         }
      ],
      "busyLines": [
         {
           "line": "Altebrel|2",
           "Date": "2025-04-11T20:30:00.000Z",
           "Finish": "27/06/2025"
         }
      ]
    }
    """
    products: Dict[str, List[str]]
    Min_Stock: Dict[str, Dict[str, Dict[int, int]]]
    Export_Stocks: Dict[str, Dict[str, Dict[int, int]]]
    Sales_Stocks: Dict[str, Dict[str, Dict[int, int]]]
    monthsCount: int
    commonBRs: List[Dict[str, Any]]
    dedicatedBRs: List[Dict[str, Any]]
    selectedDate: Optional[str] = None
    currentStocks: Optional[List[dict]] = None
    busyLines: Optional[List[dict]] = None
    initialExpiry: Dict[str, str]   # parse DD/MM/YYYY automatically



def _search_dose(prdct: str, x_dose: float) -> float:
    """
    Search for the protein per container for a given product and dose.

    Args:
        prdct (str): The name of the product.
        x_dose (float): The dose of the product.

    Returns:
        Any: The protein per container in milligrams.

    Raises:
        ValueError: If no matching row is found for the product and dose.

    """
    df_parameters = pd.read_excel(
        r"E:\\Sherkat_DeepSpring_projects\\Aryogen_Planning\\Data\\Products parameters AI.xlsx"
    )
    df_parameters = df_parameters.ffill()

    if prdct == "AryoSeven_BR":
        prdct = "AryoSeven BR"
    if prdct == "AryoSeven_RC":
        prdct = "AryoSeven RC"
        
    if prdct == "Arylia" and x_dose == 120:
        prdct = "Artenix"

    subset = df_parameters.loc[
        (df_parameters["Product name"] == prdct) & (df_parameters["Dose"] == x_dose)
    ]

    if subset.empty:
        raise ValueError(f"No row found for Product '{prdct}' with Dose '{x_dose}'!")
    return subset["Protein per container\n(mg)"].iloc[0]


def Products_Protein(
    payload: PlanPayload,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Calculate the proteins needed for the products.

    Args:
        payload: the payload object containing the plan data
    Returns:
        Tuple of three dictionaries:
            - Products_Protein_total: total protein needed for each product
            - Products_Protein_per_month: protein needed per month for each product
            - Schedule: the production schedule from the MILP solver

    """
    """
    Build a dictionary mapping product names to the initial stock amount.
    For example, if currentStocks is a list of objects or dictionaries that contain
    a field 'productDose' (like "Altebrel|25") and an 'amount', this function
    returns { "Altebrel": initial_amount, ... }.
    Adjust splitting logic as needed.
    """
    products_inventory_protein = {}
    init_stock = {}
    
    with open("E:\\Sherkat_DeepSpring_projects\\Aryogen_Planning\\Data\\Lines.json", "r") as f:
        data = json.load(f)
    
    for stock in payload.currentStocks:
        # if stock is a dict, use stock['productDose'] and stock['amount']
        prod_dose = stock['productDose']  # e.g. "Altebrel|25"
        amount = float(stock['amount'])
        # Split the product name if needed, here we assume product name is before '|'
        product = prod_dose.split("|")[0]
        dose = prod_dose.split("|")[1]
        init_stock[f"{product} {dose}"] = init_stock.get(product, 0) + amount
    
    for prdct, doses_dict in payload.Min_Stock.items():
        products_inventory_protein[f"{prdct}"] = 0
        
    # print(init_stock)
    products_protein = {}
    sales_stock_protein = {}
    export_stock_protein = {}
    products_protein_per_month = {}
    stock_amount = 0
    covers_dict = {}
    
    # 1) EXPORT side
    for prdct, doses_dict in payload.Export_Stocks.items():
        export_stock_protein.setdefault(prdct, {})
        products_protein.setdefault(prdct, {})

        for dose_str, month_map in doses_dict.items():
            numeric_dose      = float(dose_str) if "." in dose_str else int(dose_str)
            mg_per_container  = _search_dose(prdct, numeric_dose)
            export_stock_protein[prdct][f"{numeric_dose}"] = {}

            for month, qty in month_map.items():
                grams = qty * mg_per_container * 0.001

                # accumulate export by month
                export_stock_protein[prdct][f"{numeric_dose}"].setdefault(month, 0.0)
                export_stock_protein[prdct][f"{numeric_dose}"][month] += grams

    # 2) SALES side
    for prdct, doses_dict in payload.Sales_Stocks.items():
        sales_stock_protein.setdefault(prdct, {})
        products_protein.setdefault(prdct, {})

        for dose_str, month_map in doses_dict.items():
            numeric_dose      = float(dose_str) if "." in dose_str else int(dose_str)
            mg_per_container  = _search_dose(prdct, numeric_dose)

            if f'{prdct} {numeric_dose}' in data['Covers']:
                covers_dict[f'{prdct} {numeric_dose}'] = data['Covers'][f'{prdct} {numeric_dose}']
                print(f"Found Covers data for Product '{prdct}' with Dose '{numeric_dose}'. Amount: {covers_dict[f'{prdct} {numeric_dose}']}")
            else:
                raise ValueError(f"No row found for Product '{prdct}' with Dose '{numeric_dose}' in Covers data!")

            sales_stock_protein[prdct][f"{numeric_dose}"] = {}
            for month, qty in month_map.items():
                grams = qty * mg_per_container * 0.001

                # accumulate sales by month
                sales_stock_protein[prdct][f"{numeric_dose}"].setdefault(month, 0.0)
                sales_stock_protein[prdct][f"{numeric_dose}"][month] += grams

    # 3) INVENTORY (unchanged)
    for prod_dose, stock_amount in init_stock.items():
        prdct, dose_val = prod_dose.split()
        numeric_dose    = float(dose_val) if "." in dose_val else int(dose_val)
        mg_per_container = _search_dose(prdct, numeric_dose)
        grams = stock_amount * mg_per_container * 0.001
        products_inventory_protein.setdefault(prdct, 0)
        products_inventory_protein[prdct] += int(math.ceil(grams))
    
    print("Export Stock Protein:", export_stock_protein)
    print("Sales Stock Protein:", sales_stock_protein)
    print("covers_dict:", covers_dict)

    Schedule = MILP_Solver.main(
        products_protein_per_month, products_inventory_protein, payload, export_stock_protein, sales_stock_protein, covers_dict
    )
    return products_protein_per_month, Schedule


def Planner(payload: PlanPayload) -> dict[str, Dict[str, float]]:
    """
    Run the Planner agent.

    Args:
        payload: the payload object containing the plan data
    Returns:
        production_plan: dictionary with the total and monthly protein values for each product

    """
    Products_Protein_per_month, Schedule = Products_Protein(
        payload=payload
    )
    production_plan = {
        "Monthly Protein": Products_Protein_per_month,
        "Schedule": Schedule,
    }
    return production_plan


def create_timeline_chart(final_plan: list) -> str:
    """
    Generate a timeline (Gantt) chart from the final_plan.

    Args:
        final_plan (list): A list of dictionaries where each dictionary represents
                           a production run with details such as product, line used,
                           run index, and BR stages.

    Returns:
        str: A base64 encoded PNG string of the timeline chart, which visually
             represents the production schedule with bars for each stage.

    """
    product_runs = {}
    for run in final_plan:
        prod = run.get("product", "Unknown")
        product_runs.setdefault(prod, []).append(run)

    fig_height = max(6, 0.8 * len(final_plan) + 2)
    fig, ax = plt.subplots(figsize=(12, fig_height))
    y_pos = 0
    ytick_labels = []
    ytick_positions = []
    colors = plt.cm.get_cmap("tab20").colors
    label_offset = 0.3

    for prod, runs in product_runs.items():
        for run in runs:
            line_used = run.get("line_used", "N/A")
            label = f"{prod} (Line {line_used}) (Run {run['run_index']})"
            for stage in run.get("br_stages", []):
                br_name, stage_start, stage_end, start_date_str, end_date_str = stage
                try:
                    start_date = datetime.fromisoformat(start_date_str)
                    end_date = datetime.fromisoformat(end_date_str)
                except Exception:
                    continue
                width_days = (end_date - start_date).days
                color = colors[hash(br_name) % len(colors)]
                ax.barh(
                    y=y_pos,
                    width=width_days,
                    left=start_date,
                    height=0.4,
                    align="center",
                    color=color,
                    edgecolor="black",
                )
                text = f"{br_name}"
                ax.text(
                    start_date,
                    y_pos + label_offset,
                    text,
                    va="bottom",
                    ha="left",
                    fontsize=8,
                    color="black",
                    fontweight="bold",
                    rotation=45,
                )
            ytick_labels.append(label)
            ytick_positions.append(y_pos)
            y_pos += 0.8

    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.autofmt_xdate()
    ax.set_yticks(ytick_positions)
    ax.set_yticklabels(ytick_labels)
    ax.set_xlabel("Date")
    ax.set_title("Production Timeline Chart")
    ax.margins(x=0.1, y=0.1)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode("utf-8")
    return image_base64




# 4) FastAPI Endpoint
@app.post("/api/plan/")
async def receive_plan(payload: PlanPayload) -> Dict[str, Any]:
    """
    Receive the plan data from the front-end,
    runs the Planner agent, returns the final production plan.

    Args:
        payload: the plan data
    Returns:
        production_plan: dictionary with the total and monthly protein values for each product

    """
    print("************************\n", payload)
    planner = Planner(payload=payload)

    return {
        "planner": planner["Schedule"],
        "demand": planner["Schedule"]["demand"],
        "Feasible_Demand": planner["Schedule"]["feasible_capacity"],
        "Initial_Inventory_Amount": planner["Schedule"]["initial_stock"],
    }


@app.get("/api/lines")
async def get_lines() -> Dict[str, Any]:
    """
    Asynchronously retrieves production line data from a JSON file.
    This function reads the contents of a JSON file containing information
    about production lines and returns the data. If an error occurs during
    file reading or JSON parsing, an HTTPException with status code 500 is raised.

    Returns:
        dict: The data loaded from the JSON file.

    Raises:
        HTTPException: If an error occurs while reading the file or parsing the JSON.

    """
    try:
        with open(
            r"E:\\Sherkat_DeepSpring_projects\\Aryogen_Planning\\Data\\Lines.json", "r"
        ) as file:
            data = json.load(file)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Example usage with the provided payload
if __name__ == "__main__":
    payload = {
        "products": {"Altebrel": ["25", "50"], "AryoTrust": ["150", "440"]},
    }
