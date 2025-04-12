# import autogen

# import pandas as pd
# import numpy

# #getting data from front

# from typing import Dict, List, Any
# from fastapi import FastAPI
# from pydantic import BaseModel
# from fastapi.middleware.cors import CORSMiddleware

# # 2) Create our FastAPI application
# app = FastAPI()


# # Allow CORS for all origins, all methods, all headers (for development)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],      # or specify a list of allowed origins
#     allow_credentials=True,
#     allow_methods=["*"],      # allow POST, GET, OPTIONS, PUT, DELETE etc.
#     allow_headers=["*"],      # allow all headers
# )


# # 1) Define our data model (schema) using Pydantic.
# class DoseInfo(BaseModel):
#     productionDays: int
#     stocks: int

# class PlanPayload(BaseModel):
#     # This corresponds to the 'postData' structure from your Vue code:
#     # {
#     #   "products": { ... },
#     #   "Min_Stock": { ... },
#     #   "startYear": ...,
#     #   "monthsCount": ...,
#     #   "commonBRs": [ ... ],
#     #   "dedicatedBRs": [ ... ]
#     # }
#     products: Dict[str, List[str]]
#     Min_Stock: Dict[str, Dict[str, Dict[int, int]]]
#     startYear: int
#     monthsCount: int
#     commonBRs: List[Dict[str, Any]]
#     dedicatedBRs: List[Dict[str, Any]]


# # 3) Define an endpoint that will receive the data
# @app.post("/api/plan/")
# async def receive_plan(payload: PlanPayload):
#     """
#     This endpoint will receive the JSON from your Vue code.
#     FastAPI automatically parses the incoming JSON into `payload`
#     according to the PlanPayload schema above.
#     """
#     # You can do whatever you need with the data here:
# ##########################################################################3333333

#     # Planner Agents
#     class Parameters(autogen.Agent):
#         def __init__(self, **kwargs):
#             super().__init__(**kwargs)

#         async def run(self):
#             # Logic for scheduling and machine parameters
#             parameters = pd.read_excel("E:\\Sherkat_DeepSpring_projects\\GIT_MAIN_BRANCH\\guideline2actions\\guideline2actions\\src\\aryoGen\\data\\Products parameters AI.xlsx")
#             parameters = parameters.ffill()

#             def search_dose(prdct: str, x_dose: int) -> int:
#                 if parameters.loc[(parameters["Product name"] == f"{prdct}") & (parameters["Dose"] == x_dose)]:
#                     value = parameters.loc[(parameters["Product name"] == f"{prdct}") & (parameters["Dose"] == dose), "Protein per container\n(mg)"].tolist()
#                     return value[0]
#                 else: raise Exception("No object found!")


#             Products_protein = {}
#             total_demand = 0    #for calculating the total demand for a dose
#             dose_need_protein = 0       #for calculating the need of a product dose in gram

#             for prdct, doses_dict in payload.Min_Stock.items():
#                 for x_dose, month_demand in doses_dict.items():
#                     for key, value in month_demand.items():
#                         total_demand = total_demand + value
#                     dose = search_dose(prdct, x_dose)
#                     dose_need_protein = dose_need_protein + (total_demand * dose * 0.001)
#                 Products_protein[f"{prdct}"] = dose_need_protein
#             return Products_protein

#     class Quantity(autogen.Agent):
#         def __init__(self, parameter_data: dict, **kwargs):
#             super().__init__(**kwargs)

#         async def run(self):
#             # Logic to calculate or fetch quantities needed
#             return "Quantity data: Raw materials, production units, etc."

#     class Protocols(autogen.Agent):
#         def __init__(self, **kwargs):
#             super().__init__(**kwargs)

#         async def run(self):
#             # Logic to handle protocols
#             return "Protocols data: Safety procedures, regulatory standards."

#     class QAValidation(autogen.Agent):
#         def __init__(self, **kwargs):
#             super().__init__(**kwargs)

#         async def run(self):
#             # Validate quality of the production
#             return "QA Validation: Ensure batch meets quality standards."

#     class Planner(autogen.Agent):
#         def __init__(self, **kwargs):
#             super().__init__(**kwargs)
#             # Create the other agents
#             self.quantity_agent = Quantity()
#             self.protocols_agent = Protocols()
#             self.parameters_agent = Parameters()
#             self.qa_validation_agent = QAValidation()

#         async def run(self):
#             # This is where the Planner coordinates with other agents

#             # Call each agent and gather their responses
#             parameter_data = await self.parameters_agent.run()
#             quantity_data = await self.quantity_agent.run(parameter_data = parameter_data)
#             protocol_data = await self.protocols_agent.run()
#             qa_data = await self.qa_validation_agent.run()

#             # Compile production plan
#             production_plan = {
#                 "quantity": quantity_data,
#                 "protocols": protocol_data,
#                 "parameters": parameter_data,
#                 "quality_check": qa_data
#             }

#             return production_plan


#     # Main function to run all agents
#     async def main():
#         # Initialize the Planner agent
#         planner = Planner()

#         # Run the planner and gather results
#         result = await planner.run()

#         # Output the production plan
#         print(result)
#         return result

#     # Run the async main function
#     if __name__ == "__main__":
#         import asyncio
#         result = asyncio.run(main())

#     # Return output to front.
#     # return {
#     #     "message": "Plan data received successfully!",
#     #     "Plan": payload.dict(),
#     # }
#     return result


# import asyncio
# import autogen
# import re
# import pandas as pd
# import numpy as np
# import openpyxl
# import pulp
# from random import choice
# from time import sleep
# from typing import Dict, List, Any
# from fastapi import FastAPI
# from pydantic import BaseModel
# from fastapi.middleware.cors import CORSMiddleware

# # 1) FastAPI app and CORS
# app = FastAPI()
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # 2) Pydantic Model for the incoming plan data
# class PlanPayload(BaseModel):
#     """
#     Example payload structure:
#     {
#       "products": { ... },
#       "Min_Stock": {
#         "ProductA": {
#            "100": { 0: 50, 1: 70, 2: 20 },
#            "200": { 0: 10, 1: 15 }
#         },
#         "ProductB": { ... }
#       },
#       "Export_Stocks": { ... },
#       "Sales_Stocks": { ... },
#       "startYear": 2025,
#       "monthsCount": 12,
#       "commonBRs": [ ... ],
#       "dedicatedBRs": [ ... ]
#     }
#     """
#     products: Dict[str, List[str]]  # product -> list of dose strings
#     Min_Stock: Dict[str, Dict[str, Dict[int, int]]]
#     Export_Stocks: Dict[str, Dict[str, Dict[int, int]]]
#     Sales_Stocks: Dict[str, Dict[str, Dict[int, int]]]
#     startYear: int
#     monthsCount: int
#     commonBRs: List[Dict[str, Any]]
#     dedicatedBRs: List[Dict[str, Any]]

# # ------------------------------------------------
# #  ADDITIONAL IMPORTS & HELPER FUNCTIONS FOR MILP
# # ------------------------------------------------

# import openpyxl
# from openpyxl import load_workbook
# import pulp

# ############################################
# # 1) HELPER FUNCTIONS TO READ & WRITE EXCEL
# ############################################

# def load_excel_file(file_path):
#     """
#     Loads the given Excel workbook, returns the workbook
#     and references to 'QTY' and 'Stock Cover' sheets.
#     """
#     wb = openpyxl.load_workbook(file_path)
#     production_sheet = wb['QTY']
#     coverage_sheet = wb['Stock Cover']
#     return wb, production_sheet, coverage_sheet

# def find_product_row(sheet, product_name):
#     """
#     Finds the row index where product_name is in column A.
#     Returns None if not found. Assumes row 1 = header.
#     """
#     for row in range(2, sheet.max_row + 1):
#         cell_value = sheet.cell(row=row, column=1).value
#         if cell_value == product_name:
#             return row
#     return None

# def find_month_column(sheet, month_label):
#     """
#     Finds the column index with month_label in row 1.
#     Returns None if not found.
#     """
#     for col in range(2, sheet.max_column + 1):
#         header_value = sheet.cell(row=1, column=col).value
#         if header_value == month_label:
#             return col
#     return None

# # Write results to the Production (QTY) sheet
# def remove_last_word(s):
#     return ' '.join(s.split()[:-1])

# def update_production_value(sheet, product_name, month_label, production_value):
#     """
#     Updates cell in the 'QTY' sheet corresponding to (product_name, month_label).
#     """

#     product_name = remove_last_word(product_name)
#     product_row = find_product_row(sheet, product_name)
#     if product_row is None:
#         print(f"Warning: Product '{product_name}' not found in first column.")
#         return

#     month_col = find_month_column(sheet, month_label)
#     if month_col is None:
#         print(f"Warning: Month label '{month_label}' not found in header.")
#         return

#     sheet.cell(row=product_row, column=month_col).value = production_value
#     print(f"Set production of {production_value} for '{product_name}' in '{month_label}'.")

# ############################################
# # 2) BUILD PRODUCT & MONTH LISTS
# ############################################

# def get_product_list(payload):
#     """
#     Example: transforms a product 'Zytux' + dose '100' into "Zytux 100 mg".
#     """
#     tmp = []
#     for prdct, doses in payload.products.items():
#         for dose in doses:
#             dose_val = int(dose)  # or float(dose) if needed
#             tmp.append(f"{prdct} {dose_val}")
#     return tmp

# def get_month_labels(coverage_sheet):
#     """
#     Hardcoded 12 months. Must match the QTY sheet's header row.
#     """
#     return ['0401','0402','0403','0404','0405','0406','0407','0408','0409','0410','0411','0412']


# ###########################################################
# # 3) MILP MODEL: HANDLE MULTIPLE (min_batch, max_batch) RANGES
# ###########################################################
# def optimize_production_with_milp(products, batch_sizes, months):
#     """
#     A MILP that tries to minimize total production while ensuring each
#     product-month production is in exactly one of its intervals:
#       batch_sizes["Zytux 100 mg"] = [(1000,2000), (3000,5000)], etc.

#     Returns a dict: results[(product, month)] = production_value
#     """

#     # 1) Create LP problem with a minimize objective
#     prob = pulp.LpProblem("Production_Optimization", pulp.LpMinimize)

#     # 2) Decision variables
#     x_vars = {}  # integer production
#     b_vars = {}  # binary interval selectors

#     for product in products:
#         product = product + " mg"
#         intervals = batch_sizes[product]  # e.g. [(1000,2000), (3000,5000)]
#         for m_label in months:
#             var_name = f"prod_{product}_{m_label}"
#             x_vars[(product, m_label)] = pulp.LpVariable(
#                 var_name, lowBound=0, upBound=999999, cat="Integer"
#             )
#             for i, (min_b, max_b) in enumerate(intervals):
#                 b_name = f"b_{product}_{m_label}_int{i}"
#                 b_vars[(product, m_label, i)] = pulp.LpVariable(b_name, cat="Binary")

#     # 3) Constraints
#     for product in products:
#         product = product + " mg"
#         intervals = batch_sizes[product]
#         for m_label in months:
#             # EXACTLY ONE interval chosen
#             prob += pulp.lpSum(b_vars[(product, m_label, i)] for i in range(len(intervals))) == 1

#             # x >= sum(min_b * b_i)
#             prob += x_vars[(product, m_label)] >= pulp.lpSum(
#                 intervals[i][0] * b_vars[(product, m_label, i)] for i in range(len(intervals))
#             )

#             # x <= sum(max_b * b_i)
#             prob += x_vars[(product, m_label)] <= pulp.lpSum(
#                 intervals[i][1] * b_vars[(product, m_label, i)] for i in range(len(intervals))
#             )

#     # 4) Objective: minimize total production
#     for p in products:
#         p = p + " mg"
#         for m in months:
#             prob += pulp.lpSum(x_vars[(p, m)])

#     # 5) Solve
#     prob.solve()

#     # 6) Gather results
#     results = {}
#     for product in products:
#         product = product + " mg"
#         for m_label in months:
#             val = pulp.value(x_vars[(product, m_label)])
#             if val is None:
#                 val = 0
#             else:
#                 val = int(val)
#             results[(product, m_label)] = val

#     return results

# #################################
# # 4) MAIN EXECUTION / MILP CALL
# #################################
# def MILP(products_batch, payload):
#     """
#     Orchestrates reading the Excel, building the product & month lists,
#     running the MILP, then writing the solution back to the QTY sheet.
#     """
#     file_path = (
#         "E:\\Sherkat_DeepSpring_projects\\GIT_MAIN_BRANCH\\guideline2actions\\"
#         "guideline2actions\\src\\aryoGen\\data\\Production QTY AI.xlsx"
#     )

#     wb, production_sheet, coverage_sheet = load_excel_file(file_path)

#     # Build product list from the payload
#     products = get_product_list(payload)  # e.g. ["Zytux 100 mg", "Zytux 500 mg", ...]
#     months = get_month_labels(coverage_sheet)

#     # Solve MILP
#     solution_dict = optimize_production_with_milp(products, products_batch, months)

#     for product in products:
#         product = product + " mg"
#         for m_label in months:
#             production_val = solution_dict[(product, m_label)]
#             update_production_value(production_sheet, product, m_label, production_val)

#     wb.save("optimized_production.xlsx")
#     print("Optimization complete. Results saved to 'optimized_production.xlsx'.")

# if __name__ == "__MILP__":
#     MILP()

# ##########################################################
# # 5) AUTOGEN AGENTS (Parameters, QAValidation, etc.)
# ##########################################################

# class Parameters(autogen.Agent):
#     """
#     Reads an Excel file to calculate total protein needs
#     for each product & dose combination.
#     """
#     def __init__(self, payload: PlanPayload, **kwargs):
#         super().__init__(**kwargs)
#         self.payload = payload

#     def _search_dose(self, df: pd.DataFrame, prdct: str, x_dose: float) -> float:
#         subset = df.loc[(df["Product name"] == prdct) & (df["Dose"] == x_dose)]
#         if subset.empty:
#             raise ValueError(f"No row found for Product '{prdct}' with Dose '{x_dose}'!")
#         return subset["Protein per container\n(mg)"].iloc[0]

#     async def run(self) -> Dict[str, float]:
#         df_parameters = pd.read_excel(
#             "E:\\Sherkat_DeepSpring_projects\\GIT_MAIN_BRANCH\\guideline2actions\\"
#             "guideline2actions\\src\\aryoGen\\data\\Products parameters AI.xlsx"
#         ).ffill()

#         products_protein = {}
#         for prdct, doses_dict in self.payload.Min_Stock.items():
#             # We'll accumulate total demands across all doses for each product
#             dose_need_protein = 0
#             for x_dose, month_demand in doses_dict.items():
#                 total_demand = sum(month_demand.values())
#                 # Convert dose string to numeric
#                 if "." in x_dose:
#                     numeric_dose = float(x_dose)
#                 else:
#                     numeric_dose = int(x_dose)

#                 mg_per_container = self._search_dose(df_parameters, prdct, numeric_dose)
#                 # Convert mg to grams by * 0.001
#                 dose_need_protein += total_demand * mg_per_container * 0.001

#             products_protein[prdct] = dose_need_protein
#         return products_protein


# class QAValidation(autogen.Agent):
#     """
#     Ensures QA compliance, plus reads STD_BatchSize.xlsx to build
#     a multi-interval dictionary used by the MILP solver.
#     """
#     def __init__(self, payload: PlanPayload, **kwargs):
#         super().__init__(**kwargs)
#         self.payload = payload

#     async def run(self) -> Dict[str, Any]:
#         df_parameters = pd.read_excel(
#             "E:\\Sherkat_DeepSpring_projects\\GIT_MAIN_BRANCH\\guideline2actions\\"
#             "guideline2actions\\src\\aryoGen\\data\\STD_BatchSize.xlsx"
#         )

#         products_batch = {}

#         # For each product & list of doses from the payload
#         for prdct, doses in self.payload.products.items():
#             for dose in doses:
#                 fill_name = f"{prdct} {dose} mg"
#                 matched_rows = df_parameters[df_parameters["Filling"] == fill_name]
#                 if matched_rows.empty:
#                     print(f"No batch-size data found for {fill_name}, skipping.")
#                     continue

#                 # We'll parse the first matched row to get min/max intervals
#                 row_objects = matched_rows.iloc[0].tolist()

#                 # Function to extract integers from row objects
#                 def extract_numbers(row_data):
#                     numbers = []
#                     for item in row_data:
#                         if pd.isna(item):
#                             continue
#                         found_nums = re.findall(r'(\d+)', str(item))
#                         numbers.extend(map(int, found_nums))
#                     return numbers

#                 numbers_found = extract_numbers(row_objects)
#                 numbers_found = numbers_found[1:]

#                 # e.g. [1000,2000,3000,5000,...] => intervals = [(1000,2000),(3000,5000),...]
#                 intervals = []
#                 for i in range(0, len(numbers_found), 2):
#                     if i + 1 < len(numbers_found):
#                         intervals.append((numbers_found[i], numbers_found[i+1]))

#                 if not intervals:
#                     print(f"Warning: Could not form intervals for {fill_name}")
#                     continue

#                 products_batch[fill_name] = intervals

#         # Now call MILP once after building the dictionary
#         MILP(products_batch=products_batch, payload=self.payload)
#         return products_batch


# class Quantity(autogen.Agent):
#     """
#     Uses parameter data to derive or update quantity-based plans.
#     """
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)

#     async def run(self, parameter_data: Dict[str, float]) -> Dict[str, Any]:
#         return {
#             "summary": "Quantity plan based on protein needs",
#             "details": parameter_data
#         }

# class Protocols(autogen.Agent):
#     """
#     Provides any regulatory/safety protocols. Basic placeholder.
#     """
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)

#     async def run(self) -> Dict[str, str]:
#         return {"protocols_info": "Safety procedures, regulatory standards, etc."}

# class Planner(autogen.Agent):
#     """
#     Orchestrates all sub-agents, collects their data,
#     calls the QAValidation which triggers the MILP,
#     and returns a final plan.
#     """
#     def __init__(self, payload: PlanPayload, **kwargs):
#         super().__init__(**kwargs)
#         self.payload = payload
#         self.parameters_agent = Parameters(payload=self.payload)
#         self.quantity_agent = Quantity()
#         self.protocols_agent = Protocols()
#         self.qa_validation_agent = QAValidation(payload=self.payload)

#     async def run(self) -> Dict[str, Any]:
#         # 1) Calculate parameters
#         parameter_data = await self.parameters_agent.run()

#         # 2) Create quantity plan
#         quantity_data = await self.quantity_agent.run(parameter_data)

#         # 3) Protocol info
#         protocol_data = await self.protocols_agent.run()

#         # 4) QA Validation (runs MILP)
#         qa_data = await self.qa_validation_agent.run()

#         # Final production plan
#         production_plan = {
#             "parameters": parameter_data,
#             "quantity": quantity_data,
#             "protocols": protocol_data,
#             "QA_Validation": qa_data
#         }
#         return production_plan

# # 4) FastAPI Endpoint
# @app.post("/api/plan/")
# async def receive_plan(payload: PlanPayload):
#     """
#     Receives the plan data from the front-end,
#     runs the Planner agent, returns the final production plan.
#     """
#     planner = Planner(payload=payload)
#     result = await planner.run()
#     return {
#         "result": result,
#         "payload": payload
#     }


# import asyncio
# import autogen
# import re
# import pandas as pd
# import numpy as np
# import openpyxl
# import xlwings
# import pulp
# import math
# from random import choice
# from time import sleep
# from typing import Dict, List, Any
# from fastapi import FastAPI
# from pydantic import BaseModel
# from fastapi.middleware.cors import CORSMiddleware


# # 1) FastAPI app and CORS
# app = FastAPI()
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # 2) Pydantic Model for the incoming plan data
# class PlanPayload(BaseModel):
#     """
#     Example payload structure:
#     {
#       "products": { ... },
#       "Min_Stock": { ... },
#       "Export_Stocks": { ... },
#       "Sales_Stocks": { ... },
#       "startYear": 2025,
#       "monthsCount": 12,
#       "commonBRs": [ ... ],
#       "dedicatedBRs": [ ... ]
#     }
#     """
#     products: Dict[str, List[str]]  # product -> list of dose strings
#     Min_Stock: Dict[str, Dict[str, Dict[int, int]]]
#     Export_Stocks: Dict[str, Dict[str, Dict[int, int]]]
#     Sales_Stocks: Dict[str, Dict[str, Dict[int, int]]]
#     startYear: int
#     monthsCount: int
#     commonBRs: List[Dict[str, Any]]
#     dedicatedBRs: List[Dict[str, Any]]


# # ------------------------------------------------
# # ADDITIONAL IMPORTS & HELPER FUNCTIONS FOR MILP
# # ------------------------------------------------

# import openpyxl
# from openpyxl import load_workbook

# ############################################
# # 1) HELPER FUNCTIONS TO READ & WRITE EXCEL
# ############################################

# def load_excel_file(file_path):
#     """
#     Loads the given Excel workbook, returns the workbook
#     and references to 'QTY' and 'Stock Cover' sheets.
#     """
#     wb = openpyxl.load_workbook(file_path)
#     production_sheet = wb['QTY']
#     coverage_sheet = wb['Stock Cover']
#     return wb, production_sheet, coverage_sheet


# def find_product_row(sheet, product_name):
#     """
#     Finds the row index where product_name is in column A.
#     Returns None if not found. Assumes row 1 = header.
#     """
#     for row in range(2, sheet.max_row + 1):
#         cell_value = sheet.cell(row=row, column=1).value
#         if cell_value == product_name:
#             return row
#     return None


# def remove_last_word(s):
#     """ e.g. "Zytux 100 mg" -> "Zytux 100" """
#     return ' '.join(s.split()[:-1])

# def find_month_production_column(sheet, month_label):
#     """
#     Searches row 1 for 'month_label', row 2 for 'Production'.
#     Returns the column index if found, otherwise None.
#     """
#     for col in range(2, sheet.max_column + 1):
#         top_val = sheet.cell(row=1, column=col).value
#         if top_val == month_label:
#             for sub_col in range(col, col + 8):
#                 sub_val = sheet.cell(row=2, column=sub_col).value
#                 if sub_val == "Production":
#                     return sub_col
#     return None

# def find_month_coverage_cell(sheet, month_label, product_row, operator):
#     """
#     Searches row 1 for 'month_label', row 2 for 'Production'.
#     Returns the column index if found, otherwise None.
#     # """
#     # for col in range(2, sheet.max_column + 1):
#     #     top_val = sheet.cell(row=1, column=col).value
#     #     if top_val == month_label:
#     #         for sub_col in range(col, col + 8):
#     #             sub_val = sheet.cell(row=3, column=sub_col).value
#     #             if sub_val == "Cover.":
#     #                 print(sheet.cell(row=product_row,column=sub_col).value)
#     #                 return sheet.cell(row=product_row,column=sub_col).value
#     # return None
#     # Iterate over the columns (starting from column 2)
#     if operator == 1:
#         for col in range(2, 120):  # Start from column 2 (second column)
#             top_val = sheet.range(1, col).value  # Get the value in row 1 (month label)
#             if top_val == month_label:
#                 for sub_col in range(col, col + 8):
#                     sub_val = sheet.range(3, sub_col).value  # Get the value in row 3 (cover)
#                     if sub_val == "Cover.":
#                         # Get the value of the product row for the found column
#                         coverage_value = sheet.range(product_row, sub_col).value
#                         return coverage_value

#         return None

#     elif operator == 2:
#         wbook2 = sheet
#         for col in range(2, 120):  # Start from column 2 (second column)
#             top_val = wbook2.range(1, col).value  # Get the value in row 1 (month label)
#             if top_val == month_label:
#                 for sub_col in range(col, col + 8):
#                     sub_val = wbook2.range(2, sub_col).value  # Get the value in row 2 (Production)
#                     if sub_val == "Production":
#                         # Get the value of the product row for the found column
#                         production_value = wbook2.range(product_row, sub_col).value
#                         for i in range(sub_col - 8, sub_col - 3):
#                             sub_val = wbook2.range(2, i).value  # Get the value in row 2 (Production)
#                             if sub_val == "Production":
#                                 keeper = i
#                         return production_value,keeper,sub_col

#         return None


# def update_production_value(sheet, product_name, month_label, production_value):
#     product_no_mg = remove_last_word(product_name)  # or remove mg if needed
#     product_row = find_product_row(sheet, product_no_mg)
#     if product_row is None:
#         print(f"Warning: Product '{product_no_mg}' not found in first column.")
#         return

#     prod_col = find_month_production_column(sheet, month_label)
#     if prod_col is None:
#         print(f"Warning: Month '{month_label}' sub-col 'Production' not found.")
#         return

#     sheet.cell(row=product_row, column=prod_col).value = production_value
#     print(f"Set production={production_value} for product='{product_no_mg}' in '{month_label}' (Production).")


# ############################################
# # 2) BUILD PRODUCT & MONTH LISTS
# ############################################

# def get_product_list(payload):
#     """
#     Transforms a product 'Zytux' + dose '100' into "Zytux 100" (no "mg" here).
#     The code will add " mg" later in the MILP function or where needed.
#     """
#     tmp = []
#     for prdct, doses in payload.products.items():
#         for dose in doses:
#             dose_val = int(dose)  # or float(dose) if needed
#             tmp.append(f"{prdct} {dose_val}")
#     return tmp


# def get_month_labels():
#     """
#     Hardcoded 12 months. Must match the QTY sheet's header row.
#     """
#     return ['0401','0402','0403','0404','0405','0406','0407','0408','0409','0410','0411','0412','0501']


# ###########################################################
# # 3) MILP MODEL: HANDLE MULTIPLE (min_batch, max_batch) RANGES
# ###########################################################
# def optimize_production_with_milp(products, batch_sizes, months):
#     """
#     A MILP that tries to minimize total production while ensuring each
#     product-month production is in exactly one of its intervals:
#       batch_sizes["Zytux 100 mg"] = [(1000,2000), (3000,5000)], etc.

#     Returns a dict: results[(product, month)] = production_value
#     """
#     prob = pulp.LpProblem("Production_Optimization", pulp.LpMinimize)

#     # 2) Decision variables
#     x_vars = {}
#     b_vars = {}

#     for product in products:
#         product_with_mg = product + " mg"
#         intervals = batch_sizes[product_with_mg]  # e.g. {"Zytux 100 mg": [...]}
#         for m_label in months:
#             var_name = f"prod_{product_with_mg}_{m_label}"
#             x_vars[(product_with_mg, m_label)] = pulp.LpVariable(
#                 var_name, lowBound=0, upBound=999999, cat="Integer"
#             )
#             for i, (min_b, max_b) in enumerate(intervals):
#                 b_name = f"b_{product_with_mg}_{m_label}_int{i}"
#                 b_vars[(product_with_mg, m_label, i)] = pulp.LpVariable(b_name, cat="Binary")

#     # 3) Constraints
#     for product in products:
#         product_with_mg = product + " mg"
#         intervals = batch_sizes[product_with_mg]
#         for m_label in months:
#             prob += pulp.lpSum(
#                 b_vars[(product_with_mg, m_label, i)]
#                                for i in range(len(intervals))) == 1

#             # x >= sum(min_b * b_i)
#             prob += x_vars[(product_with_mg, m_label)] >= pulp.lpSum(
#                 intervals[i][0] * b_vars[(product_with_mg, m_label, i)]
#                 for i in range(len(intervals))
#             )

#             # x <= sum(max_b * b_i)
#             prob += x_vars[(product_with_mg, m_label)] <= pulp.lpSum(
#                 intervals[i][1] * b_vars[(product_with_mg, m_label, i)]
#                 for i in range(len(intervals))
#             )

#     # 4) Objective: minimize sum of all x_vars
#     #    We'll do a single expression summing across all product-month
#     all_x_vars = [x_vars[(p + " mg", m)] for p in products for m in months]
#     prob += pulp.lpSum(all_x_vars)

#     # 5) Solve
#     prob.solve()

#     # 6) Gather results
#     results = {}
#     for product in products:
#         product_with_mg = product + " mg"
#         for m_label in months:
#             val = pulp.value(x_vars[(product_with_mg, m_label)])
#             if val is None:
#                 val = 0
#             else:
#                 val = int(val)
#             results[(product_with_mg, m_label)] = val

#     return results


# #################################
# # 4) MAIN EXECUTION / MILP CALL
# #################################
# def MILP(products_batch, payload):
#     """
#     Orchestrates reading the Excel, building the product & month lists,
#     running the MILP, then writing the solution back to the QTY sheet.
#     """
#     file_path = (
#         "E:\\Sherkat_DeepSpring_projects\\GIT_MAIN_BRANCH\\guideline2actions\\"
#         "guideline2actions\\src\\aryoGen\\data\\Production QTY AI.xlsx"
#     )

#     wb, production_sheet, coverage_sheet = load_excel_file(file_path)

#     products = get_product_list(payload)  # e.g. ["Zytux 100", "Zytux 500", ...]
#     months = get_month_labels()

#     # Solve MILP
#     solution_dict = optimize_production_with_milp(products, products_batch, months)

#     # Write results to QTY sheet
#     for product_no_mg in products:
#         product_with_mg = product_no_mg + " mg"
#         for m_label in months:
#             production_val = solution_dict[(product_with_mg, m_label)]
#             update_production_value(production_sheet, product_with_mg, m_label, production_val)

#     wb.save("optimized_production.xlsx")
#     print("MILP Production plan saved to 'optimized_production.xlsx'.")

#     # OPTIONAL: Also do coverage-based iteration if desired
#     # e.g. adjust_production_until_coverage_in_range("optimized_production.xlsx", step=10, max_iters=20)

#     return solution_dict


# ##########################################################
# # 5) ADDITIONAL COVERAGE CHECK / ITERATION LOGIC
# ##########################################################

# def parse_min_max_range(range_str):
#     """
#     Expects a string like '3.5-5.0'. Returns (3.5, 5.0).
#     """
#     parts = re.split(r'[-–]', str(range_str))
#     if len(parts) != 2:
#         return None, None
#     min_val = float(parts[0])
#     max_val = float(parts[1])
#     return (min_val, max_val)

# def read_min_max_safety(sheet):
#     """
#     Reads Column A (product name), Column B (Min-Max string) from 'Stock Cover'
#     e.g. '3.5-5.0', returns dict: { 'Zytux 100': (3.5, 5.0), ... }
#     """
#     min_max_dict = {}
#     for row in range(2, sheet.max_row + 1):
#         product_name = sheet.cell(row=row, column=1).value
#         range_str = sheet.cell(row=row, column=14).value  # e.g. '3.5-5.0'
#         if product_name and range_str:
#             mn, mx = parse_min_max_range(range_str)
#             if mn is not None and mx is not None:
#                 min_max_dict[product_name] = (mn, mx)
#     return min_max_dict

# def read_coverage_value(sheet, month, product_name):
#     """
#     Reads coverage from Column C for the given product_name in 'Stock Cover'.
#     (Adjust if your coverage is in another column.)
#     """
#     row_idx = find_product_row(sheet, product_name)
#     if row_idx is None:
#         return None

#     app2 = xlwings.App(visible=False)
#     wbook = app2.books.open("E:\\Sherkat_DeepSpring_projects\\GIT_MAIN_BRANCH\\guideline2actions\\guideline2actions\\src\\aryoGen\\data\\Production QTY AI.xlsx")
#     wbook2 = wbook.sheets['QTY']
#     coverage_val = find_month_coverage_cell(sheet=wbook2, month_label=month,product_row=row_idx,operator=1)
#     if coverage_val == '-':
#         return '-'
#     else:
#         # coverage_val = round(coverage_val)
#         # Close the workbook and quit Excel
#         wbook.close()
#         app2.quit()

#         if coverage_val is None:
#             return None
#         return float(coverage_val)

# def read_coverage_value_for_edition(sheet,wbook2, month, product_name):
#     """
#     (Adjust if your coverage is in another column.)
#     """
#     row_idx = find_product_row(sheet, product_name)
#     if row_idx is None:
#         return None

#     coverage_val = find_month_coverage_cell(sheet=wbook2, month_label=month,product_row=row_idx,operator=1)
#     if coverage_val == '-':
#         return '-'
#     else:
#         coverage_val = float(coverage_val)
#         # coverage_val = round(coverage_val)
#         # Close the workbook and quit Excel

#         if coverage_val is None:
#             return None
#         return float(coverage_val)


# def adjust_production_in_qty(sheet,sheet2, month, product_name, delta, coverage_ranges):
#     """
#     Increments or decrements the production in QTY for product_name (Column B).
#     This is a simplistic approach if you have only one 'production' column.
#     """

#     row_idx = find_product_row(sheet, product_name)
#     if row_idx is None:
#         print(f"[WARN] {product_name} not found in QTY for coverage iteration.")
#         return

#     current_val,keeper,sub_col = find_month_coverage_cell(sheet=sheet2,month_label=month,product_row=row_idx,operator = 2)

#     if current_val == None:
#         current_val = 0
#     current_val = float(current_val)
#     # current_val = round(current_val, 1)

#     new_val = max(0, current_val + delta)

#     return new_val, current_val,row_idx,keeper,sub_col


# def adjust_production_until_coverage_in_range(file_path, smple_list, step, max_iters, products_batch):
#     """
#     Iterates up to max_iters times. For each product in 'Stock Cover':
#       - read min/max coverage from Column B
#       - read coverage from Column C
#       - if coverage < min => +step
#         coverage > max => -step
#       - Save & rely on Excel formulas for coverage recalculation
#     """
#     wb, production_sheet, coverage_sheet = load_excel_file(file_path)
#     coverage_ranges = read_min_max_safety(coverage_sheet)

#     production_sheet2 = load_workbook(file_path, data_only=True)
#     production_sheet2 = production_sheet2['QTY']

#     smple_lst = []
#     for i in smple_list:
#         i = remove_last_word(i)
#         smple_lst.append(i)

#     product_list = smple_lst  # e.g. ["Zytux 100", "Altebrel 25"]
#     months = get_month_labels()


#     import os
#     file_path2 = "E:\\Sherkat_DeepSpring_projects\\GIT_MAIN_BRANCH\\guideline2actions\\guideline2actions\\src\\aryoGen\\data\\Production QTY AI.xlsx"

#     # Check if the file is read-only
#     if os.access(file_path2, os.W_OK):
#         pass
#     else:
#         print("File is read-only. Attempting to change...")

#         # Remove the read-only attribute (only works on Windows)
#         os.chmod(file_path2, 0o666)  # This removes the read-only flag

#     app2 = xlwings.App(visible=False)
#     wbook = app2.books.open("E:\\Sherkat_DeepSpring_projects\\GIT_MAIN_BRANCH\\guideline2actions\\guideline2actions\\src\\aryoGen\\data\\Production QTY AI - Copy.xlsx")

#     production_sheet3 = load_workbook(file_path2, data_only=True)
#     production_sheet3 = production_sheet3['QTY']

#     print(products_batch)
#     max_iters = 50
#     for iteration in range(max_iters):
#         print(f"\n=== Coverage Iteration {iteration +1} ===")
#         in_range_count = 0
#         total_products = len(product_list)
#         months = months


#         step = 500
#         step2 = 200

#         for_break_iteration_below = len(product_list) * len(months)
#         break_flag = 0
#         break_flag2 = 0

#         for p_name in product_list:
#             for month in months:
#                 (mn, mx) = coverage_ranges[p_name]
#                 print("month : ", month)

#                 if os.access(file_path2, os.W_OK):
#                     print("File is not read-only")
#                 else:
#                     print("File is read-only. Attempting to change...")

#                     # Remove the read-only attribute (only works on Windows)

#                     os.chmod(file_path2, 0o666)  # This removes the read-only flag

#                 cov_val = read_coverage_value_for_edition(sheet=production_sheet2,wbook2=wbook.sheets['QTY'], month=month, product_name=p_name)
#                 if cov_val == '-':
#                     continue
#                 else:
#                     if cov_val is None:
#                         print(f"[WARN] No coverage value found for '{p_name}'. Skipping.")
#                         continue

#                     if cov_val < mn:
#                         print(f"[{p_name}] coverage = {cov_val} < min = {mn} => +{step} production")

#                         new_val, current_val,row_idx,keeper,sub_col = adjust_production_in_qty(sheet=production_sheet2,sheet2=wbook.sheets['QTY'], month = month,product_name=p_name, delta=step, coverage_ranges = coverage_ranges)

#                         wbook.sheets['QTY'].range(row_idx, keeper).value = new_val   #make an iteration here for optimizing
#                         wbook.sheets['QTY'].range(row_idx, sub_col).value = new_val   #make an iteration here for optimizing
#                         wbook.save("E:\\Sherkat_DeepSpring_projects\\GIT_MAIN_BRANCH\\guideline2actions\\guideline2actions\\src\\aryoGen\\data\\Production QTY AI - Copy.xlsx")
#                         print(f"Updated '{p_name}' production from {current_val} to {new_val} (delta={step}).")
#                         break

#                     elif cov_val > mx:
#                         print(f"[{p_name}] coverage={cov_val:.2f} > max={mx} => -{step2} production")

#                         new_val, current_val,row_idx,keeper, sub_col = adjust_production_in_qty(sheet=production_sheet2,sheet2=wbook.sheets['QTY'], month = month,product_name=p_name, delta = -step2, coverage_ranges = coverage_ranges)

#                         wbook.sheets['QTY'].range(row_idx, keeper).value = new_val   #make an iteration here for optimizing
#                         wbook.sheets['QTY'].range(row_idx, sub_col).value = new_val   #make an iteration here for optimizing
#                         wbook.save("E:\\Sherkat_DeepSpring_projects\\GIT_MAIN_BRANCH\\guideline2actions\\guideline2actions\\src\\aryoGen\\data\\Production QTY AI - Copy.xlsx")
#                         print(f"Updated '{p_name}' production from {current_val} to {new_val} (delta={-step2}).")
#                         break

#                     else:
#                         break_flag += 1
#                         print(f"[{p_name}] coverage={cov_val:.2f} in [{mn}, {mx}] => OK")

#             break_flag2 += 1
#             in_range_count += 1
#             if break_flag2 * break_flag == for_break_iteration_below:
#                 break
#         if break_flag2 * break_flag == for_break_iteration_below:
#             break

#     wbook.close()
#     app2.quit()
#     print("here")


# ##########################################################
# # 6) AUTOGEN AGENTS (Parameters, QAValidation, Planner...)
# ##########################################################

# class Parameters(autogen.Agent):
#     """
#     Reads an Excel file (AI.xlsx) to calculate total protein for each product/dose.
#     """
#     def __init__(self, payload: PlanPayload, **kwargs):
#         super().__init__(**kwargs)
#         self.payload = payload

#     def _search_dose(self, df: pd.DataFrame, prdct: str, x_dose: float) -> float:
#         subset = df.loc[(df["Product name"] == prdct) & (df["Dose"] == x_dose)]
#         if subset.empty:
#             raise ValueError(f"No row found for Product '{prdct}' with Dose '{x_dose}'!")
#         return subset["Protein per container\n(mg)"].iloc[0]

#     async def run(self) -> Dict[str, float]:
#         df_parameters = pd.read_excel(
#             "E:\\Sherkat_DeepSpring_projects\\GIT_MAIN_BRANCH\\guideline2actions\\"
#             "guideline2actions\\src\\aryoGen\\data\\Products parameters AI.xlsx"
#         ).ffill()

#         products_protein = {}
#         for prdct, doses_dict in self.payload.Min_Stock.items():
#             dose_need_protein = 0
#             for x_dose, month_demand in doses_dict.items():
#                 total_demand = sum(month_demand.values())
#                 if "." in x_dose:
#                     numeric_dose = float(x_dose)
#                 else:
#                     numeric_dose = int(x_dose)

#                 mg_per_container = self._search_dose(df_parameters, prdct, numeric_dose)
#                 dose_need_protein += total_demand * mg_per_container * 0.001

#             products_protein[prdct] = dose_need_protein
#         return products_protein


# class QAValidation(autogen.Agent):
#     """
#     Ensures QA compliance, plus reads STD_BatchSize.xlsx
#     to build a multi-interval dictionary used by the MILP solver.
#     """
#     def __init__(self, payload: PlanPayload, **kwargs):
#         super().__init__(**kwargs)
#         self.payload = payload

#     async def run(self) -> Dict[str, Any]:
#         df_parameters = pd.read_excel(
#             "E:\\Sherkat_DeepSpring_projects\\GIT_MAIN_BRANCH\\guideline2actions\\"
#             "guideline2actions\\src\\aryoGen\\data\\STD_BatchSize.xlsx"
#         )

#         products_batch = {}
#         # Build intervals for each product + dose
#         for prdct, doses in self.payload.products.items():
#             for dose in doses:
#                 fill_name = f"{prdct} {dose} mg"
#                 matched_rows = df_parameters[df_parameters["Filling"] == fill_name]
#                 if matched_rows.empty:
#                     print(f"No batch-size data found for {fill_name}, skipping.")
#                     continue

#                 row_objects = matched_rows.iloc[0].tolist()

#                 def extract_numbers(row_data):
#                     numbers = []
#                     for item in row_data:
#                         if pd.isna(item):
#                             continue
#                         found_nums = re.findall(r'(\d+)', str(item))
#                         numbers.extend(map(int, found_nums))
#                     return numbers

#                 numbers_found = extract_numbers(row_objects)
#                 # If you want to skip the first number, do numbers_found = numbers_found[1:] if needed
#                 intervals = []
#                 for i in range(0, len(numbers_found), 2):
#                     if i+1 < len(numbers_found):
#                         intervals.append((numbers_found[i+1], numbers_found[i+2]))

#                 if not intervals:
#                     print(f"Warning: Could not form intervals for {fill_name}")
#                     continue

#                 products_batch[fill_name] = intervals

#         # Run MILP to set a baseline production plan
#         MILP(products_batch=products_batch, payload=self.payload)

#         # Optionally, we could do coverage iteration here
#         # For example:
#         coverage_file = (
#             "E:\\Sherkat_DeepSpring_projects\\GIT_MAIN_BRANCH\\guideline2actions\\"
#             "guideline2actions\\src\\aryoGen\\data\\Production QTY AI.xlsx"
#         )
#         smple_list = []
#         for i in products_batch.keys():
#             smple_list.append(i)

#         adjust_production_until_coverage_in_range(
#             coverage_file, smple_list, step=10, max_iters=20, products_batch = products_batch
#         )
#         return {"products_batch": products_batch}


# class Quantity(autogen.Agent):
#     """
#     Uses parameter data to derive or update quantity-based plans.
#     """
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)

#     async def run(self, parameter_data: Dict[str, float]) -> Dict[str, Any]:
#         return {
#             "summary": "Quantity plan based on protein needs",
#             "details": parameter_data
#         }


# class Protocols(autogen.Agent):
#     """
#     Basic placeholder for regulatory or safety protocols.
#     """
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)

#     async def run(self) -> Dict[str, str]:
#         return {"protocols_info": "Safety procedures, regulatory standards, etc."}


# class Planner(autogen.Agent):
#     """
#     Orchestrates all sub-agents, collects their data,
#     calls QAValidation which triggers the MILP & coverage iteration,
#     then returns the final plan.
#     """
#     def __init__(self, payload: PlanPayload, **kwargs):
#         super().__init__(**kwargs)
#         self.payload = payload
#         self.parameters_agent = Parameters(payload=self.payload)
#         self.quantity_agent = Quantity()
#         self.protocols_agent = Protocols()
#         self.qa_validation_agent = QAValidation(payload=self.payload)

#     async def run(self) -> Dict[str, Any]:
#         # 1) Calculate parameters
#         parameter_data = await self.parameters_agent.run()

#         # 2) Create quantity plan
#         quantity_data = await self.quantity_agent.run(parameter_data)

#         # 3) Protocol info
#         protocol_data = await self.protocols_agent.run()

#         # 4) QA Validation => runs MILP => coverage iteration
#         qa_data = await self.qa_validation_agent.run()

#         # Combine results
#         production_plan = {
#             "parameters": parameter_data,
#             "quantity": quantity_data,
#             "protocols": protocol_data,
#             "QA_Validation": qa_data
#         }
#         return production_plan


# # 4) FastAPI Endpoint
# @app.post("/api/plan/")
# async def receive_plan(payload: PlanPayload):
#     """
#     Receives the plan data from the front-end,
#     runs the Planner agent, returns the final production plan.
#     """
#     planner = Planner(payload=payload)
#     result = await planner.run()
#     return {
#         "result": result,
#         "payload": payload

#     }
