import numpy
import pandas as pd


def Total_Need_gram():
    Sales_Budget = pd.read_excel(
        "E:\\Sherkat_DeepSpring_projects\\GIT_MAIN_BRANCH\\guideline2actions\\guideline2actions\\src\\aryoGen\\data\\Sales_Budget_AI.xlsx"
    )
    Sales_Budget.iloc[0:15, 2:]
    # Sales_Budget = Sales_Budget.drop(columns=["Gender"])
    Sales_Budget["sum"] = Sales_Budget.iloc[0:15, 2:].sum(axis=1)
    # Extract the number using a regular expression
    Sales_Budget["Dose"] = Sales_Budget["Name"].str.extract(r"(\d+\.?\d*)")
    # Convert the extracted number to integer (optional)
    Sales_Budget["Dose"] = Sales_Budget["Dose"].astype(float)
    Sales_Budget["SafetyStock"] = Sales_Budget["sum"] * Sales_Budget["Dose"] / 4000
    Sales_Budget["SB_Total(gr)"] = (
        (Sales_Budget["Dose"] * Sales_Budget["sum"]) / 1000
    ).apply(numpy.ceil) + Sales_Budget["SafetyStock"]

    Export = pd.read_excel(
        "E:\\Sherkat_DeepSpring_projects\\GIT_MAIN_BRANCH\\guideline2actions\\guideline2actions\\src\\aryoGen\\data\\Export_AI.xlsx"
    )
    Export["Dose"] = Export["Dosage"].str.extract(r"(\d+\.?\d*)")
    Export["Dose"] = Export["Dose"].astype(float)
    Export["E_Total(gr)"] = (Export["Dose"] * Export["QTY"] / 1000).apply(numpy.ceil)
    Export["Complete_Name"] = Export["Medicine"] + " " + Export["Dosage"]

    Export["Are_In_SB_too"] = Export["Complete_Name"][
        Export["Complete_Name"].isin(Sales_Budget["Name"])
    ]
    Sales_Budget["Are_In_Export_too"] = Sales_Budget["Name"][
        Sales_Budget["Name"].isin(Export["Complete_Name"])
    ]

    E_SB_Result = {}
    SB_Result = {}
    E_Result = {}

    # Export & Sales Budget:
    # for those products in Export that they are in SB too, calc the summation of their SB_total and E_total
    for row in Export.iterrows():
        # Check condition
        if row[1][11] == row[1][12]:  # a product is in both Ex & Sales Budget
            value2 = Export.loc[
                Export["Are_In_SB_too"] == row[1][12]
            ]  # those rows that their Are_In_SB_too value is same as row[1][12]
            value3 = 0

            for option in value2[
                "E_Total(gr)"
            ]:  # summation of all E_Total(gr)'s that their Are_In_SB_too value is same as row[1][12]    #all the export demand
                value3 = value3 + option

            value1 = Sales_Budget.loc[Sales_Budget["Name"] == row[1][12]]

            E_SB_Result[f"{row[1][11]}"] = (
                value1["SB_Total(gr)"].values + value3
            )  # total gram values appended

        else:
            # Just Export Products appended:
            if f"{row[1][11]}" in E_Result:
                E_Result[f"{row[1][11]}"] = row[1][10] + E_Result[f"{row[1][11]}"]
            else:
                E_Result[f"{row[1][11]}"] = row[1][10]

    # Just Sales Budget Products appended:
    # Iterate over rows in Sales_Budget
    for row in Sales_Budget.iterrows():
        # Check condition
        if row[1][0] != row[1][18]:
            if f"{row[1][0]}" in SB_Result:
                SB_Result[f"{row[1][0]}"] = row[1][17] + SB_Result[f"{row[1][0]}"]
            else:
                SB_Result[f"{row[1][0]}"] = row[1][17]

    Complete_Result = {**E_SB_Result, **E_Result, **SB_Result}

    for k in Complete_Result.keys():
        if type(Complete_Result[f"{k}"]) != float:
            Complete_Result[f"{k}"] = float(Complete_Result[f"{k}"].item())

    for element in Complete_Result:
        print(element)


Total_Need_gram()
