import json
import math
import uuid
from collections import deque
from datetime import date, datetime, timedelta
from ortools.sat.python import cp_model

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from textwrap import indent

SHELF_LIFE = 24  # Shelf life in months
DAYS_PER_MONTH = 30
TOTAL_MONTHS = None
BASE_DATE_FOR_PLANNING = None
MAX_RUNS = 100  # Maximum number of production runs per product
bigM = 1_000_000

from datetime import datetime

def parse_date_isoformat(date_str: str) -> datetime:
    """
    Parse an ISO-like date string, e.g. '2025-04-11T20:30:00.000Z',
    into a Python datetime object.
    """
    # Adjust the format as needed if your string is slightly different
    # For 'YYYY-MM-DDTHH:MM:SS.000Z', we can do:
    return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")

def parse_date_dd_mm_yyyy(date_str: str) -> datetime:
    """
    Parse a date string in 'DD/MM/YYYY' format, e.g. '01/02/2026',
    into a Python datetime object.
    """
    return datetime.strptime(date_str, "%d/%m/%Y")

def set_total_months(new_month_count: int):
    """
    Sets the global TOTAL_MONTHS based on the user input in main().
    """
    global TOTAL_MONTHS
    TOTAL_MONTHS = new_month_count


def parse_base_date(date_str: str) -> date:
    """
    Convert an ISO-like string (e.g. 2025-04-01T20:30:00.000Z) into a Python date object.
    """
    # Example parsing using datetime.strptime for the format including 'Z'
    # Adjust if your format is slightly different.
    dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    return dt.date()


# --- NEW GLOBAL VARIABLE ---


def set_base_date_for_planning(new_date: date):
    global BASE_DATE_FOR_PLANNING
    BASE_DATE_FOR_PLANNING = new_date


def day_to_date(day_offset: int) -> str:
    """
    Convert a day offset to an ISO formatted date string, based on the global
    BASE_DATE_FOR_PLANNING instead of a fixed 2026-01-01.
    """
    global BASE_DATE_FOR_PLANNING
    if BASE_DATE_FOR_PLANNING is None:
        # fallback if not set, or raise an error
        raise ValueError(
            "BASE_DATE_FOR_PLANNING is not set. Call set_base_date_for_planning() first."
        )

    actual_date = BASE_DATE_FOR_PLANNING + timedelta(days=day_offset)
    return actual_date.isoformat()


def parse_volume(br_name: str) -> float:
    """
    Parses the volume from a batch record name.

    The function extracts the leading numeric characters from the batch record name,
    which are assumed to represent the volume. The batch record name is expected to
    have the format where the volume is the first part of the string, separated by a
    hyphen.

    Args:
        br_name (str): The batch record name from which to extract the volume.

    Returns:
        float: The extracted volume as a float. Returns 0.0 if no numeric characters
               are found at the beginning of the batch record name.

    """
    chunk = br_name.split("-")[0]
    digits = ""
    for ch in chunk:
        if ch.isdigit():
            digits += ch
        else:
            break
    return float(digits) if digits else 0.0

def build_solver_inputs_from_payload(
    busyLines: list,
    selectedDate: str
):
    """
    Returns two dictionaries:
      - existing_stock: { productName : currentAmount, ... }
      - lineBusyUntil:  { lineID : dayOffset, ... }

    The dayOffset is the integer (days) from the selectedDate to the line's Finish date.
    """
    # 1) Parse the selectedDate as our base for day offsets
    base_date = parse_date_isoformat(selectedDate)  # e.g. 2025-04-11T20:30:00.000Z
    
    # 3) Build lineBusyUntil
    #    We'll parse "line": "Arylia|2" => lineID = 2. Then parse "Finish": "01/02/2026" => day offset from base_date
    lineBusyUntil = {}
    for bline in busyLines:
        line_str = bline['line']         # e.g. "Arylia|2"
        finish_str = bline['Finish']     # e.g. "01/02/2026"

        # parse out the line ID (the second part after '|')
        # "Arylia|2" => splitted = ["Arylia", "2"]
        splitted = line_str.split('|')
        l_id = int(splitted[1])  # convert "2" -> 2

        # parse the finish date
        finish_date = parse_date_dd_mm_yyyy(finish_str)  # e.g. datetime(2026, 2, 1)
        
        # compute day offset: how many days from base_date to finish_date
        day_offset = (finish_date - base_date).days
        
        lineBusyUntil[l_id] = day_offset
    
    return lineBusyUntil

# --- NEW CODE: A specialized planner for AryoSeven_RC ---
def build_schedule_for_AryoSevenRC(data: dict, demand: dict[str, dict]):
    """
    A separate planner that handles AryoSeven_RC production,
    because it uses 'TFs' instead of 'BRs', and yields a fixed 3.3 grams per run
    instead of a volume-based approach.

    Returns:
       final_plan_RC: a list of dictionaries describing the runs and stages
       inv_traj_RC: inventory trajectory for AryoSeven_RC

    """
    # We'll assume line 0 is active for AryoSeven_RC if "status" == "active".
    # Quick checks:
    if "AryoSeven_RC" not in demand:
        print("No AryoSeven_RC demand. Skipping specialized RC planner.")
        return [], {}

    rc_conf_list = data.get("AryoSeven_RC")  # e.g. [base_conf, {lines: [...]}]
    if not rc_conf_list or len(rc_conf_list) < 2:
        print("Incomplete config for AryoSeven_RC in Lines.json.")
        return [], {}

    base_conf_rc = rc_conf_list[0]
    lines_conf_rc = rc_conf_list[1]
    line_list_rc = lines_conf_rc.get("lines", [])
    active_line0_conf = None
    for li in line_list_rc:
        if li.get("id") == 0 and li.get("status") == "active":
            active_line0_conf = li
            break

    if not active_line0_conf:
        print("No active line 0 found for AryoSeven_RC. Can't schedule.")
        return [], {}

    # 1) Build a minimal CP-SAT or some simpler approach.
    model = cp_model.CpModel()

    # We'll assume each run can produce 3.3 grams. We'll create boolean variables:
    use_run = {}
    finish_time = {}
    for r in range(MAX_RUNS):
        use_run[r] = model.NewBoolVar(f"run_aryoSevenRC_{r}")
        finish_time[r] = model.NewIntVar(0, bigM, f"fin_aryoSevenRC_{r}")

    # We won't fully define all parallel stage logic here, but let's outline a notion:
    # Suppose each run takes a fixed total time = sum of all TF durations + some optional overlaps.
    # We'll gather durations from active_line0_conf["TFs"].
    tfs_map = active_line0_conf["TFs"]  # e.g. { "75":4, "175":3, ... }
    # We can define a rough total time for each run:
    total_tf_time = sum(tfs_map.values())  # ignoring overlaps for brevity
    # Additionally, 1 day for "Cell_Thawing & SF"
    cell_thaw_time = base_conf_rc.get("Cell_Thawing & SF", 1)
    # So each run might take cell_thaw_time + total_tf_time days:
    run_duration = cell_thaw_time + total_tf_time

    # We'll create a chain of runs with no overlap, for example:
    # (In real code, you might do more constraints to handle parallel runs or resource usage.)
    # prev_end = model.NewIntVar(0, bigM, "prev_end_init")
    # model.Add(prev_end == 0)  # Start at day 0
    # for r in range(MAX_RUNS):
    #     st = model.NewIntVar(0, bigM, f"start_aryoSevenRC_{r}")
    #     en = finish_time[r]
    #     # If run is used => st >= prev_end
    #     model.Add(st >= prev_end).OnlyEnforceIf(use_run[r])
    #     # If run is not used => st = 0, en = 0
    #     model.Add(st == 0).OnlyEnforceIf(use_run[r].Not())
    #     model.Add(en == st + run_duration - 1).OnlyEnforceIf(use_run[r])

    #     # Link prev_end for the next run:
    #     if r < MAX_RUNS - 1:
    #         next_st = model.NewIntVar(0, bigM, f"start_aryoSevenRC_{r + 1}")
    #         model.Add(prev_end == en + 1).OnlyEnforceIf(use_run[r])
    #         # If run[r] is not used, we keep prev_end the same. So let's do something like:
    #         tmp = model.NewIntVar(0, bigM, f"tmp_{r}")
    #         model.Add(tmp == prev_end).OnlyEnforceIf(use_run[r].Not())
    #         # But to keep it simple, we skip advanced logic here.
    start_vars = {}    # Dictionary to hold independent start times
    for r in range(MAX_RUNS):
        use_run[r] = model.NewBoolVar(f"run_aryoSevenRC_{r}")
        start_vars[r] = model.NewIntVar(0, bigM, f"start_aryoSevenRC_{r}")
        finish_time[r] = model.NewIntVar(0, bigM, f"fin_aryoSevenRC_{r}")
        # If a run is used, finish_time is set relative to its start
        model.Add(finish_time[r] == start_vars[r] + run_duration - 1).OnlyEnforceIf(use_run[r])
        # Otherwise, you can fix start and finish to 0 if not used.
        model.Add(start_vars[r] == 0).OnlyEnforceIf(use_run[r].Not())
        model.Add(finish_time[r] == 0).OnlyEnforceIf(use_run[r].Not())

    intervals = []
    for r in range(MAX_RUNS):
        interval = model.NewOptionalIntervalVar(start_vars[r], run_duration, finish_time[r], use_run[r], f"interval_aryoSevenRC_{r}")
        intervals.append(interval)
    model.AddNoOverlap(intervals)

    # 2) Demand constraints, usage variables, etc.
    # For each run => produces 3.3 grams => partial usage across months, expiration, ...
    # We'll define usage[(r, m)], isValid[(r, m)], etc. just like your scenario B approach.
    usage = {}
    isValid = {}
    expiration_date = {}
    SHELF_LIFE_RC = 24  # months
    # We map run -> produce_protein = 3.3 * use_run[r]
    produced_protein_run = {}
    for r in range(MAX_RUNS):
        # If run is active => produce 3.3
        # We'll create an IntVar for produced_protein_run. We'll store it as integer scaled by 100 for example if needed
        # For simplicity let's store as an IntVar with an upper bound 4 to store ceil(3.3).
        produced_protein_run[r] = model.NewIntVar(3, 4, f"protein_run_{r}")
        # enforce produced_protein_run[r] = 3.3 if run is used, else 0
        # We'll do approximate integer approach:
        # 3.3 -> we store as 3.  If you want a real approach, you'd use intervals or linear approx.
        # For a quick approach:
        # model.Add(produced_protein_run[r] == 3).OnlyEnforceIf(use_run[r])
        # model.Add(produced_protein_run[r] == 0).OnlyEnforceIf(use_run[r].Not())

        # expiration day => finish_time[r] + SHELF_LIFE_RC * 30
        expiration_date[r] = model.NewIntVar(0, bigM, f"exp_run_{r}")
        model.Add(expiration_date[r] == finish_time[r] + SHELF_LIFE_RC * 30)

        for m in range(1, TOTAL_MONTHS + 1):
            usage[(r, m)] = model.NewIntVar(0, bigM, f"usage_{r}_{m}")
            isValid[(r, m)] = model.NewBoolVar(f"isValid_{r}_{m}")

    # Sum usage <= produced
    for r in range(MAX_RUNS):
        model.Add(
            sum(usage[(r, m)] for m in range(1, TOTAL_MONTHS + 1))
            <= produced_protein_run[r]
        )

    # Demand coverage
    # demand["AryoSeven_RC"][m] might exist
    for m in range(1, TOTAL_MONTHS + 1):
        dem_m = int(math.ceil(demand["AryoSeven_RC"].get(m, 0)))
        model.Add(sum(usage[(r, m)] for r in range(MAX_RUNS)) >= dem_m)

    # isValid => run finishes by month end, not expired at month start
    # same approach as your scenario B
    for r in range(MAX_RUNS):
        F = finish_time[r]
        E = expiration_date[r]
        for m in range(1, TOTAL_MONTHS + 1):
            valid = isValid[(r, m)]
            month_end = m * 30
            month_start = (m - 1) * 30
            model.Add(F <= month_end).OnlyEnforceIf(valid)
            model.Add(E > month_start).OnlyEnforceIf(valid)
            # usage zero if not valid
            model.Add(usage[(r, m)] <= bigM * valid)

    # Minimization: keep it consistent with your logic, or simpler
    # e.g. minimize max finish_time plus sum of active runs
    max_finish = model.NewIntVar(0, bigM, "max_finish_rc")
    model.AddMaxEquality(max_finish, [finish_time[r] for r in range(MAX_RUNS)])
    total_runs = model.NewIntVar(0, MAX_RUNS, "total_runs")
    model.Add(total_runs == sum(use_run[r] for r in range(MAX_RUNS)))

    # Some objective: minimize max_finish + 1000*total_runs
    model.Minimize(max_finish + 1000 * total_runs)

    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = True
    solver.parameters.max_time_in_seconds = 100.0
    solver.parameters.num_search_workers = 2
    status = solver.Solve(model)
    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print("No feasible solution for AryoSeven_RC.")
        return [], {}

    # Build final_plan_RC
    final_plan_RC = []
    for r in range(MAX_RUNS):
        print(solver.Value(finish_time[r]))
        if solver.Value(use_run[r]) == 0:
            continue
        fday = solver.Value(finish_time[r])
        expd = solver.Value(expiration_date[r])
        monthly_usage_rc = {}
        for m in range(1, TOTAL_MONTHS + 1):
            val = solver.Value(usage[(r, m)])
            if val > 0:
                monthly_usage_rc[m] = val
        final_plan_RC.append(
            {
                "product": "AryoSeven_RC",
                "run_index": r,
                "line_used": 0,
                "finish_day": fday,
                "finish_date": day_to_date(fday),
                "monthly_usage": monthly_usage_rc,
                "liters": 0.0,  # not relevant
                "production_month": None,
                # produce_protein = 3 if used, or partial usage
                "produced_protein": float(solver.Value(produced_protein_run[r])),
                "br_stages": [],  # or "tf_stages" if you want to add them
                "release_day": fday,
                "expiration_date": expd,
                "expiration_date_str": day_to_date(expd),
            }
        )

    print(final_plan_RC)
    # Build inventory from usage
    inv_traj_RC: dict[str, dict[int, int]] = {}
    inv_traj_RC["AryoSeven_RC"] = {}
    current_inv = 0
    for m in range(1, TOTAL_MONTHS + 1):
        total_prod_m = sum(solver.Value(usage[(r, m)]) for r in range(MAX_RUNS))
        dem_m = int(math.ceil(demand["AryoSeven_RC"].get(m, 0)))
        current_inv = current_inv + total_prod_m - dem_m
        inv_traj_RC["AryoSeven_RC"][m] = current_inv

    return final_plan_RC, inv_traj_RC


def build_schedule_with_inventory(
    data: dict[str, dict],
    demand: dict[str, dict],
    products_inventory_protein,
    payload
):
    model = cp_model.CpModel()

    print("\nProduct Inventory Entered By User =>",products_inventory_protein)
    # 1) Filter relevant products
    all_prods = list(data["Common_Lines"].keys())
    products = [p for p in all_prods if p in demand]
    if not products:
        print("No matching products. Exiting.")
        return [], {}

    # 2) Gather product parameters
    product_lines: dict[str, dict] = {}
    product_factor: dict[str, float] = {}
    product_harvest: dict[str, int] = {}
    base_configs: dict[str, dict] = {}
    for p in products:
        conf_list = data[p]  # e.g., [base_conf, {"lines": [...]}]
        base_conf = conf_list[0]
        base_configs[p] = base_conf
        lines_conf = conf_list[1]
        factor = base_conf.get("Protein_per_1000L_BR", 0.0)
        harvest = base_conf.get("Harvest", 0)
        if "lines" in lines_conf:
            lines_list = lines_conf["lines"]
        else:
            lines_list = lines_conf.get("RC", [])
        active_lines: dict[str, dict] = {}
        for li in lines_list:
            if li.get("status") == "active":
                active_lines[li["id"]] = li
        product_lines[p] = active_lines
        product_factor[p] = factor
        product_harvest[p] = harvest

    # 3) Decision variables for production runs
    activate_run: dict[tuple[str, int], cp_model.IntVar] = {}
    use_line: dict[tuple[str, int, str], cp_model.IntVar] = {}
    stage_start: dict[
        tuple[str, int, str, int], cp_model.IntVar
    ] = {}  # (p, r, l_id, stage_key): chain stages (thawing and BR stages)
    stage_end: dict[tuple[str, int, str, int], cp_model.IntVar] = {}
    finish_time: dict[tuple[str, int], cp_model.IntVar] = {}
    resources: dict[tuple[str, str], list[cp_model.IntervalVar]] = {}
    harvest_vars: dict[
        tuple[str, int, str, int], tuple[cp_model.IntVar, cp_model.IntVar]
    ] = {}  # (p, r, l_id, br_stage_key): (harv_st, harv_en)
    hold_vars: dict[
        tuple[str, int, str, int], tuple[cp_model.IntVar, cp_model.IntVar]
    ] = {}  # (p, r, l_id, br_stage_key): (hold_st, hold_en)
    mab_vars: dict[
        tuple[str, int, str, int, int], tuple[cp_model.IntVar, cp_model.IntVar]
    ] = {}  # (p, r, l_id, br_stage_key, mab_idx): (mab_st, mab_en)
    fu_vars: dict[
        tuple[str, int, str, int, str], tuple[cp_model.IntVar, cp_model.IntVar]
    ] = {}  # (p, r, l_id, br_stage_key, fu_name): (fu_st, fu_en)
    lineBusyUntil = build_solver_inputs_from_payload(payload.busyLines, payload.selectedDate)

    
    NEGATIVE_BOUND = -180

    for p in products:
        lines_dict = product_lines[p]
        thawing = base_configs[p].get("Cell_Thawing & SF", 0)
        for r in range(MAX_RUNS):
            activate_run[(p, r)] = model.NewBoolVar(f"activate_{p}_{r}")
            for l_id in lines_dict:
                use_line[(p, r, l_id)] = model.NewBoolVar(f"use_{p}_{r}_l{l_id}")
            model.Add(
                sum(use_line[(p, r, l)] for l in lines_dict) == activate_run[(p, r)]
            )

            candidate_finishes = []

            for l_id, l_conf in lines_dict.items():
                br_map = l_conf["BRs"]
                overlaps = l_conf.get("Overlaps") or {}
                br_names = list(br_map.keys())
                n_br = len(br_names)

                # Build chain stages: stage 0 = thawing; then BR stages (integer keys)
                chain_keys = []
                chain_keys.append(0)
                thaw_st = model.NewIntVar(
                    NEGATIVE_BOUND, 50000, f"thaw_{p}_{r}_l{l_id}_0"
                )
                thaw_en = model.NewIntVar(
                    NEGATIVE_BOUND, 50000, f"thaw_{p}_{r}_l{l_id}_0"
                )
                
                if l_id in lineBusyUntil:
                    # The day offset after which line l_id is free
                    free_day = lineBusyUntil[l_id]
                    # Ensure we don't start the thawing stage before line is free
                    model.Add(thaw_st >= free_day).OnlyEnforceIf(use_line[(p, r, l_id)])

                stage_start[(p, r, l_id, 0)] = thaw_st
                stage_end[(p, r, l_id, 0)] = thaw_en
                thaw_interval = model.NewOptionalIntervalVar(
                    thaw_st,
                    thawing - 1,
                    thaw_en,
                    use_line[(p, r, l_id)],
                    f"thaw_interval_{p}_{r}_l{l_id}_0",
                )
                res_id = (l_id, "CellThawing & SF")
                if res_id not in resources:
                    resources[res_id] = []
                resources[res_id].append(thaw_interval)

                # Determine harvest rules.
                n_harvest = l_conf.get("N_Harvest", 1)
                if n_harvest == 2:
                    candidate_indices = [
                        i for i, br in enumerate(br_names) if parse_volume(br) >= 1000
                    ]
                    if len(candidate_indices) >= 2:
                        first_harvest_index = candidate_indices[-2]
                        second_harvest_index = candidate_indices[-1]
                    else:
                        first_harvest_index = second_harvest_index = n_br - 1
                else:
                    first_harvest_index = n_br - 1

                # Process each BR stage.
                for i, brn in enumerate(br_names):
                    stage_key = i + 1
                    chain_keys.append(stage_key)
                    dur = br_map[brn]  # Duration without harvest/hold/mab/follow-up.
                    st_var = model.NewIntVar(
                        NEGATIVE_BOUND, 50000, f"st_{p}_{r}_l{l_id}_{stage_key}"
                    )
                    en_var = model.NewIntVar(
                        NEGATIVE_BOUND, 50000, f"en_{p}_{r}_l{l_id}_{stage_key}"
                    )
                    stage_start[(p, r, l_id, stage_key)] = st_var
                    stage_end[(p, r, l_id, stage_key)] = en_var
                    interval = model.NewOptionalIntervalVar(
                        st_var,
                        dur - 1,
                        en_var,
                        use_line[(p, r, l_id)],
                        f"interval_{p}_{r}_l{l_id}_{stage_key}",
                    )
                    res_id = (l_id, brn)
                    if res_id not in resources:
                        resources[res_id] = []
                    resources[res_id].append(interval)

                    # Determine if this BR stage qualifies for harvest.
                    add_harvest = False
                    if n_harvest == 1 and i == n_br - 1:
                        add_harvest = True
                    elif n_harvest == 2 and i in [
                        first_harvest_index,
                        second_harvest_index,
                    ]:
                        add_harvest = True
                    if add_harvest:
                        # Harvest stage (one day) starting one day after BR stage end.
                        harv_st = model.NewIntVar(
                            NEGATIVE_BOUND,
                            50000,
                            f"harv_st_{p}_{r}_l{l_id}_{stage_key}",
                        )
                        harv_en = model.NewIntVar(
                            NEGATIVE_BOUND,
                            50000,
                            f"harv_en_{p}_{r}_l{l_id}_{stage_key}",
                        )
                        model.Add(harv_st == en_var + 1).OnlyEnforceIf(
                            use_line[(p, r, l_id)]
                        )
                        model.Add(harv_en == harv_st).OnlyEnforceIf(
                            use_line[(p, r, l_id)]
                        )
                        harv_interval = model.NewOptionalIntervalVar(
                            harv_st,
                            1 - 1,
                            harv_en,
                            use_line[(p, r, l_id)],
                            f"harv_interval_{p}_{r}_l{l_id}_{stage_key}",
                        )
                        res_id_h = (l_id, f"Harvest {brn}")
                        if res_id_h not in resources:
                            resources[res_id_h] = []
                        resources[res_id_h].append(harv_interval)
                        harvest_vars[(p, r, l_id, stage_key)] = (harv_st, harv_en)

                        # Optional Hold stage.
                        if l_conf.get("Hold", 0) in [1, "Yes"]:
                            hold_st = model.NewIntVar(
                                NEGATIVE_BOUND,
                                50000,
                                f"hold_st_{p}_{r}_l{l_id}_{stage_key}",
                            )
                            hold_en = model.NewIntVar(
                                NEGATIVE_BOUND,
                                50000,
                                f"hold_en_{p}_{r}_l{l_id}_{stage_key}",
                            )
                            model.Add(hold_st == harv_en + 1).OnlyEnforceIf(
                                use_line[(p, r, l_id)]
                            )
                            model.Add(hold_en == hold_st).OnlyEnforceIf(
                                use_line[(p, r, l_id)]
                            )
                            hold_interval = model.NewOptionalIntervalVar(
                                hold_st,
                                1 - 1,
                                hold_en,
                                use_line[(p, r, l_id)],
                                f"hold_interval_{p}_{r}_l{l_id}_{stage_key}",
                            )
                            res_id_hold = (l_id, f"Hold {brn}")
                            if res_id_hold not in resources:
                                resources[res_id_hold] = []
                            resources[res_id_hold].append(hold_interval)
                            hold_vars[(p, r, l_id, stage_key)] = (hold_st, hold_en)

                        # Mab stages.
                        mabs_dict = l_conf.get("Mabs", {})
                        mab_key = f"After {brn}"
                        if mab_key in mabs_dict:
                            num_mabs = mabs_dict[mab_key]
                            if (p, r, l_id, stage_key) in hold_vars:
                                ref_expr = hold_vars[(p, r, l_id, stage_key)][1]
                            else:
                                ref_expr = en_var + 1  # Ensure separation from Harvest.
                            mab_en_prev = None
                            for mab_idx in range(1, num_mabs + 1):
                                mab_st = model.NewIntVar(
                                    NEGATIVE_BOUND,
                                    50000,
                                    f"mab_st_{p}_{r}_l{l_id}_{stage_key}_{mab_idx}",
                                )
                                mab_en = model.NewIntVar(
                                    NEGATIVE_BOUND,
                                    50000,
                                    f"mab_en_{p}_{r}_l{l_id}_{stage_key}_{mab_idx}",
                                )
                                if mab_idx == 1:
                                    model.Add(mab_st == ref_expr)
                                else:
                                    model.Add(mab_st == mab_en_prev + 1)
                                model.Add(mab_en == mab_st).OnlyEnforceIf(
                                    use_line[(p, r, l_id)]
                                )
                                mab_interval = model.NewOptionalIntervalVar(
                                    mab_st,
                                    1 - 1,
                                    mab_en,
                                    use_line[(p, r, l_id)],
                                    f"mab_interval_{p}_{r}_l{l_id}_{stage_key}_{mab_idx}",
                                )
                                res_id_mab = (l_id, f"Mab {brn} {mab_idx}")
                                if res_id_mab not in resources:
                                    resources[res_id_mab] = []
                                resources[res_id_mab].append(mab_interval)
                                mab_vars[(p, r, l_id, stage_key, mab_idx)] = (
                                    mab_st,
                                    mab_en,
                                )
                                mab_en_prev = mab_en

                        # --- MODIFIED CODE: Handling "SS's" for AryoSeven_BR ---
                        # Check for "SS's" dict
                        sss_dict = l_conf.get("SS's", {})
                        sss_key = f"After {brn}"
                        if sss_key in sss_dict:
                            num_sss = sss_dict[sss_key]
                            # If there's a hold stage, reference its end. Else reference en_var + 1
                            if (p, r, l_id, stage_key) in hold_vars:
                                ref_expr = hold_vars[(p, r, l_id, stage_key)][1]
                            else:
                                ref_expr = en_var + 1  # or the harvest end, etc.
                            sss_en_prev = None
                            for sss_idx in range(1, num_sss + 1):
                                sss_st = model.NewIntVar(
                                    NEGATIVE_BOUND,
                                    50000,
                                    f"sss_st_{p}_{r}_l{l_id}_{stage_key}_{sss_idx}",
                                )
                                sss_en = model.NewIntVar(
                                    NEGATIVE_BOUND,
                                    50000,
                                    f"sss_en_{p}_{r}_l{l_id}_{stage_key}_{sss_idx}",
                                )
                                if sss_idx == 1:
                                    model.Add(sss_st == ref_expr)
                                else:
                                    model.Add(sss_st == sss_en_prev + 1)
                                model.Add(sss_en == sss_st).OnlyEnforceIf(
                                    use_line[(p, r, l_id)]
                                )
                                sss_interval = model.NewOptionalIntervalVar(
                                    sss_st,
                                    1 - 1,
                                    sss_en,
                                    use_line[(p, r, l_id)],
                                    f"sss_interval_{p}_{r}_l{l_id}_{stage_key}_{sss_idx}",
                                )
                                # Provide resource ID if needed, or skip if it doesn't block anything
                                res_id_sss = (l_id, f"SS's {brn} {sss_idx}")
                                resources.setdefault(res_id_sss, []).append(
                                    sss_interval
                                )

                                # store for final plan printing
                                mab_vars[(p, r, l_id, stage_key, 1000 + sss_idx)] = (
                                    sss_st,
                                    sss_en,
                                )  # or define a new dict if you prefer
                                sss_en_prev = sss_en

                        
                        # FOLLOW-UP STAGES.
                        # Handle FU stages, including those with same start dates
                        fu_key = f"Follow_Up_{brn}"
                        if fu_key in l_conf:
                            fu_dict = l_conf[fu_key]
                            fu_over = l_conf.get(f"{fu_key}_Overlaps", None)
                            same_start_dict = l_conf.get(f"{fu_key}_SameStarts", {})

                            # Ensure same_start_dict is a dictionary
                            if isinstance(same_start_dict, str):
                                # If it's a string, treat it as a mapping (e.g., "DP_QC_Test & Visual Insp." to "1")
                                same_start_dict = {same_start_dict: 1}
                            elif not isinstance(same_start_dict, dict):
                                # If it's neither a dictionary nor a string, raise an error
                                raise ValueError(
                                    f"Expected a dictionary or string for 'SameStarts', but got {type(same_start_dict)}"
                                )

                            # Determine reference for FU start (last completed stage, whether Hold or Mab)
                            # Determine reference for FU start (last completed stage, whether Hold or Mab)
                            if any(
                                (p, r, l_id, stage_key, idx) in mab_vars
                                for idx in range(1, mabs_dict.get(mab_key, 0) + 1)
                            ):
                                # If there are Mab stages, use the end of the last Mab stage as the reference
                                idx = 1
                                while (p, r, l_id, stage_key, idx) in mab_vars:
                                    idx += 1
                                ref_fu = mab_vars[(p, r, l_id, stage_key, idx - 1)][1]
                                ref_fu = ref_fu + 1
                            elif (p, r, l_id, stage_key) in hold_vars:
                                # If there is a Hold stage, use the end of the Hold stage as the reference
                                ref_fu = hold_vars[(p, r, l_id, stage_key)][1]
                            else:
                                # Otherwise, use the end of the Harvest stage as the reference
                                ref_fu = harvest_vars[(p, r, l_id, stage_key)][1]

                            # Start FU stages 1 day after the reference stage ends
                            fu_prev_end = model.NewIntVar(
                                NEGATIVE_BOUND,
                                50000,
                                f"fu_ref_{p}_{r}_l{l_id}_{stage_key}",
                            )
                            model.Add(fu_prev_end == ref_fu + 1)

                            # Create an ordered list of FU stages as they appear in the dictionary
                            fu_stage_order = list(fu_dict.keys())

                            # Extracting the key and value
                            for key, value in same_start_dict.items():
                                # Split the key and strip whitespace
                                parts = [part.strip() for part in key.split("&")]
                                # Create the desired list
                                result = parts + [value]

                            # Adjust FU stage scheduling to ensure it follows the last Mab stage of the same BR (e.g., 4500).
                            fu_prev_end = model.NewIntVar(
                                NEGATIVE_BOUND,
                                50000,
                                f"fu_ref_{p}_{r}_l{l_id}_{stage_key}",
                            )
                            # Instead of directly using mab_idx, we try candidate indices:
                            # Instead of directly iterating over candidate indices, do this:

                            # Create a list to collect all Mab (and SS) stage end times for the current (p, r, l_id, stage_key)
                            candidate_end_exprs = []
                            for key in mab_vars:
                                if key[0] == p and key[1] == r and key[2] == l_id and key[3] == stage_key:
                                    candidate_end_exprs.append(mab_vars[key][1])
                            # Similarly, if you want to also include SS's tracked with offsets (e.g., keys with 1000+ something)
                            for key in mab_vars:
                                if key[0] == p and key[1] == r and key[2] == l_id and key[3] == stage_key and key[4] >= 1000:
                                    candidate_end_exprs.append(mab_vars[key][1])

                            if not candidate_end_exprs:
                                raise KeyError(f"No Mab or SS stage found for (p, r, l_id, stage_key): {(p, r, l_id, stage_key)}")

                            # Create a new CP variable to hold the maximum end time among Mab (and SS) stages for the current BR stage.
                            last_stage_end = model.NewIntVar(NEGATIVE_BOUND, 50000, f"last_stage_end_{p}_{r}_{l_id}_{stage_key}")
                            model.AddMaxEquality(last_stage_end, candidate_end_exprs)

                            # Define fu_prev_end to start FU stages 2 days after the maximum Mab/SS stage end time.
                            fu_prev_end = model.NewIntVar(NEGATIVE_BOUND, 50000, f"fu_ref_{p}_{r}_l{l_id}_{stage_key}")
                            model.Add(fu_prev_end == last_stage_end + 2)

                            # found_key = None
                            # max_candidates = 10  # adjust this value as necessary
                            # for idx in range(1, max_candidates + 1):
                            #     key_normal = (p, r, l_id, stage_key, idx)
                            #     key_ss = (p, r, l_id, stage_key, 1000 + idx)
                            #     if key_normal in mab_vars:
                            #         found_key = key_normal
                            #         break
                            #     elif key_ss in mab_vars:
                            #         found_key = key_ss
                            #         break
                            # if found_key is None:
                            #     raise KeyError(f"No Mab or SS stage found for keys with base {(p, r, l_id, stage_key)} up to {max_candidates}")

                            # # Use the found reference end time to set fu_prev_end (with your desired offset, here +2)
                            # model.Add(fu_prev_end == mab_vars[found_key][1] + 2)

                            for fu_name in fu_stage_order:

                                # 1) Check if fu_name is in any same-start group.
                                matched_group = None
                                for same_stages_str, _ in same_start_dict.items():
                                    # e.g. same_stages_str = "DP_QC_Test & Visual Insp."
                                    stages_list = same_stages_str.split(" & ")
                                    if fu_name in stages_list:
                                        matched_group = same_stages_str
                                        break
                                
                                if matched_group is not None:
                                    # === We have a same-start group that includes fu_name ===
                                    stages_to_sync = matched_group.split(" & ")

                                    # Check if any stage in this group is already scheduled (has an entry in fu_vars).
                                    assigned_start = None
                                    for stg in stages_to_sync:
                                        stage_key_ = (p, r, l_id, stage_key, stg)
                                        if stage_key_ in fu_vars:
                                            # Found a stage already scheduled -> use its start for everyone else
                                            assigned_start = fu_vars[stage_key_][0]
                                            break

                                    if assigned_start is None:
                                        # No stage in the group is scheduled yet -> define a new start = fu_prev_end + 1
                                        assigned_start = model.NewIntVar(
                                            NEGATIVE_BOUND,
                                            50000,
                                            f"common_start_{p}_{r}_l{l_id}_{stage_key}_{matched_group}",
                                        )
                                        model.Add(
                                            assigned_start == fu_prev_end
                                        ).OnlyEnforceIf(use_line[(p, r, l_id)])

                                    # Schedule all stages in the group that are not already scheduled.
                                    for stg in stages_to_sync:
                                        stage_key_ = (p, r, l_id, stage_key, stg)
                                        if stage_key_ not in fu_vars:
                                            fu_st = model.NewIntVar(
                                                NEGATIVE_BOUND,
                                                50000,
                                                f"fu_st_{p}_{r}_l{l_id}_{stage_key}_{stg}",
                                            )
                                            fu_en = model.NewIntVar(
                                                NEGATIVE_BOUND,
                                                50000,
                                                f"fu_en_{p}_{r}_l{l_id}_{stage_key}_{stg}",
                                            )
                                            # All same-start stages begin at the assigned_start.
                                            model.Add(
                                                fu_st == assigned_start
                                            ).OnlyEnforceIf(use_line[(p, r, l_id)])
                                            model.Add(
                                                fu_en == fu_st + fu_dict[stg] - 1
                                            ).OnlyEnforceIf(use_line[(p, r, l_id)])

                                            fu_interval = model.NewOptionalIntervalVar(
                                                fu_st,
                                                fu_dict[stg] - 1,
                                                fu_en,
                                                use_line[(p, r, l_id)],
                                                f"fu_interval_{p}_{r}_l{l_id}_{stage_key}_{stg}",
                                            )
                                            res_id_fu = (l_id, f"FU {brn} {stg}")
                                            resources.setdefault(res_id_fu, []).append(
                                                fu_interval
                                            )

                                            fu_vars[stage_key_] = (fu_st, fu_en)
                                    # Update fu_prev_end to one day after the latest finish in the group.
                                    group_end = model.NewIntVar(
                                        NEGATIVE_BOUND,
                                        50000,
                                        f"group_end_{p}_{r}_l{l_id}_{stage_key}_{matched_group}",
                                    )
                                    group_ends = [
                                        fu_vars[(p, r, l_id, stage_key, stg)][1]
                                        for stg in stages_to_sync
                                    ]
                                    model.AddMaxEquality(group_end, group_ends)
                                    fu_prev_end = group_end + 1

                                    # Skip further processing for this fu_name (already handled).
                                    continue
                                
                                # If the stage is already in result, skip it.
                                if fu_name in result:
                                    continue

                                # For individual FU stages not in same-start groups:
                                # Determine if this is the first FU stage or not.
                                idx = fu_stage_order.index(fu_name)
                                if fu_stage_order[idx - 1] in result:
                                    # First FU stage (or previous already handled): start at fu_prev_end.
                                    fu_prev_end = (
                                        fu_vars[
                                            (
                                                p,
                                                r,
                                                l_id,
                                                stage_key,
                                                fu_stage_order[idx - 1],
                                            )
                                        ][1]
                                        + 1
                                    )

                                # For subsequent stages, enforce overlap if defined.
                                prev_fu_name = fu_stage_order[idx - 1]
                                # Look for an overlap definition between prev_fu_name and fu_name.
                                overlap_key = f"{prev_fu_name} & {fu_name}"
                                if isinstance(fu_over, dict):
                                    ov_val = fu_over.get(overlap_key, None)
                                    if ov_val is None:
                                        # Try the reverse order.
                                        overlap_key = f"{fu_name} & {prev_fu_name}"
                                        ov_val = fu_over.get(overlap_key, None)
                                else:
                                    # When fu_over is a simple value (like "None")
                                    ov_val = fu_over

                                # Now apply FU overlap logic similar to BR overlaps.
                                fu_st = model.NewIntVar(
                                    NEGATIVE_BOUND,
                                    50000,
                                    f"fu_st_{p}_{r}_l{l_id}_{stage_key}_{fu_name}",
                                )
                                fu_en = model.NewIntVar(
                                    NEGATIVE_BOUND,
                                    50000,
                                    f"fu_en_{p}_{r}_l{l_id}_{stage_key}_{fu_name}",
                                )

                                if ov_val is not None and ov_val != "None":
                                    if ov_val == 1:
                                        # No gap between stages.
                                        model.Add(fu_st == fu_prev_end).OnlyEnforceIf(
                                            use_line[(p, r, l_id)]
                                        )
                                    elif ov_val == "Full":
                                        # FU stage ends exactly when the previous stage ends (i.e., no gap)
                                        model.Add(fu_st == fu_prev_end).OnlyEnforceIf(
                                            use_line[(p, r, l_id)]
                                        )
                                        model.Add(fu_en == fu_prev_end).OnlyEnforceIf(
                                            use_line[(p, r, l_id)]
                                        )
                                    else:
                                        # Numeric overlap: next stage starts earlier.
                                        model.Add(
                                            fu_st == fu_prev_end - ov_val
                                        ).OnlyEnforceIf(use_line[(p, r, l_id)])
                                else:
                                    # No overlap defined: schedule sequentially (i.e. start immediately after previous FU stage).
                                    model.Add(fu_st == fu_prev_end).OnlyEnforceIf(
                                        use_line[(p, r, l_id)]
                                    )
                                    
                                # End time of the current FU stage.
                                model.Add(
                                    fu_en == fu_st + fu_dict[fu_name] - 1
                                ).OnlyEnforceIf(use_line[(p, r, l_id)])
                                # Create the interval.
                                fu_interval = model.NewOptionalIntervalVar(
                                    fu_st,
                                    fu_dict[fu_name] - 1,
                                    fu_en,
                                    use_line[(p, r, l_id)],
                                    f"fu_interval_{p}_{r}_l{l_id}_{stage_key}_{fu_name}",
                                )
                                res_id_fu = (l_id, f"FU {brn} {fu_name}")
                                resources.setdefault(res_id_fu, []).append(fu_interval)
                                fu_vars[(p, r, l_id, stage_key, fu_name)] = (
                                    fu_st,
                                    fu_en,
                                )
                                # Update fu_prev_end to be one day after this FU stage ends.
                                fu_prev_end = fu_en + 1

                # End processing each BR stage.
                # Enforce consecutive constraints on the chain (thawing and BR stages).
                for idx in range(len(chain_keys) - 1):
                    curr_key = chain_keys[idx]
                    next_key = chain_keys[idx + 1]
                    if idx == 0:
                        model.Add(
                            stage_start[(p, r, l_id, next_key)]
                            == stage_end[(p, r, l_id, curr_key)]
                        ).OnlyEnforceIf(use_line[(p, r, l_id)])
                    else:
                        prev_br = br_names[curr_key - 1]
                        next_br = br_names[next_key - 1]
                        ov_val = overlaps.get(f"{prev_br} & {next_br}") or overlaps.get(
                            f"{next_br} & {prev_br}"
                        )
                        if ov_val is not None and ov_val != "None":
                            if ov_val == 1:
                                model.Add(
                                    stage_start[(p, r, l_id, next_key)]
                                    == stage_end[(p, r, l_id, curr_key)]
                                ).OnlyEnforceIf(use_line[(p, r, l_id)])
                            elif ov_val == "Full":
                                model.Add(
                                    stage_end[(p, r, l_id, next_key)]
                                    == stage_end[(p, r, l_id, curr_key)]
                                ).OnlyEnforceIf(use_line[(p, r, l_id)])
                            else:
                                model.Add(
                                    stage_start[(p, r, l_id, next_key)]
                                    == stage_end[(p, r, l_id, curr_key)] - ov_val + 1
                                ).OnlyEnforceIf(use_line[(p, r, l_id)])
                        else:
                            model.Add(
                                stage_start[(p, r, l_id, next_key)]
                                >= stage_end[(p, r, l_id, curr_key)]
                            ).OnlyEnforceIf(use_line[(p, r, l_id)])

                # Compute finish time for this line as the maximum of:
                # - the end of the last chain stage,
                # - any Harvest, Hold, Mab, or Follow-Up stage end times.
                if len(chain_keys) > 0:
                    chain_finish = stage_end[(p, r, l_id, chain_keys[-1])]
                else:
                    chain_finish = thaw_en
                harvest_ends_line = []
                for key in range(1, len(br_names) + 1):
                    if (p, r, l_id, key) in harvest_vars:
                        harvest_ends_line.append(harvest_vars[(p, r, l_id, key)][1])
                hold_ends_line = []
                for key in range(1, len(br_names) + 1):
                    if (p, r, l_id, key) in hold_vars:
                        hold_ends_line.append(hold_vars[(p, r, l_id, key)][1])
                mab_ends_line = []
                for key in range(1, len(br_names) + 1):
                    idx = 1
                    while (p, r, l_id, key, idx) in mab_vars:
                        mab_ends_line.append(mab_vars[(p, r, l_id, key, idx)][1])
                        idx += 1
                fu_ends_line = []
                for key in range(1, len(br_names) + 1):
                    for fu_key in [
                        k
                        for k in fu_vars
                        if k[0] == p and k[1] == r and k[2] == l_id and k[3] == key
                    ]:
                        fu_ends_line.append(fu_vars[fu_key][1])
                if harvest_ends_line or hold_ends_line or mab_ends_line or fu_ends_line:
                    fin_l = model.NewIntVar(
                        NEGATIVE_BOUND, 50000, f"fin_{p}_{r}_l{l_id}"
                    )
                    candidates = (
                        [chain_finish]
                        + harvest_ends_line
                        + hold_ends_line
                        + mab_ends_line
                        + fu_ends_line
                    )
                    model.AddMaxEquality(fin_l, candidates)
                else:
                    fin_l = chain_finish

                candidate = model.NewIntVar(
                    NEGATIVE_BOUND, 50000, f"candidate_finish_{p}_{r}_{l_id}"
                )
                model.Add(candidate == fin_l).OnlyEnforceIf(use_line[(p, r, l_id)])
                model.Add(candidate == NEGATIVE_BOUND).OnlyEnforceIf(
                    use_line[(p, r, l_id)].Not()
                )
                candidate_finishes.append(candidate)

            if candidate_finishes:
                ft = model.NewIntVar(NEGATIVE_BOUND, 50000, f"finish_{p}_{r}")
                model.AddMaxEquality(ft, candidate_finishes)
                finish_time[(p, r)] = ft
            else:
                finish_time[(p, r)] = model.NewIntVar(0, 0, f"finish_{p}_{r}_null")

    # Resource no-overlap.
    for _, intervals in resources.items():
        model.AddNoOverlap(intervals)

    # 4) Production Calculation: volume -> liters -> protein.
    line_final_vol: dict[tuple[str, str], float] = {}
    for p in products:
        for l_id, l_conf in product_lines[p].items():
            br_names = list(l_conf["BRs"].keys())
            if not br_names:
                line_final_vol[(p, l_id)] = 0
                continue
            last_vol = parse_volume(br_names[-1])
            if len(br_names) >= 2:
                sec_vol = parse_volume(br_names[-2])
                if last_vol >= 1000 and sec_vol >= 1000:
                    line_final_vol[(p, l_id)] = last_vol + sec_vol
                else:
                    line_final_vol[(p, l_id)] = last_vol
            else:
                line_final_vol[(p, l_id)] = last_vol

    produced_liters: dict[tuple[str, int], cp_model.IntVar] = {}
    for p in products:
        for r in range(MAX_RUNS):
            partial_vars = []
            for l_id in product_lines[p]:
                vol = int(line_final_vol[(p, l_id)])
                pLit = model.NewIntVar(0, vol, f"pLit_{p}_{r}_l{l_id}")
                model.AddMultiplicationEquality(pLit, [use_line[(p, r, l_id)], vol])
                partial_vars.append(pLit)
            totLit = model.NewIntVar(0, bigM, f"totLit_{p}_{r}")
            model.Add(totLit == sum(partial_vars))
            produced_liters[(p, r)] = totLit

    produced_protein_int: dict[tuple[str, int], cp_model.IntVar] = {}
    for p in products:
        f_int = int(round(product_factor[p]))
        for r in range(MAX_RUNS):
            prot = model.NewIntVar(0, bigM, f"prot_{p}_{r}")
            produced_protein_int[(p, r)] = prot
            plit = produced_liters[(p, r)]
            model.Add(plit * f_int >= prot * 1000)
            diff = model.NewIntVar(0, bigM, f"diff_{p}_{r}")
            model.Add(diff == plit * f_int - prot * 1000)
            model.Add(diff < 1000)

    # ================================
    # INVENTORY + PARTIAL USAGE (Scenario B)
    # ================================

    # 1) Remove the old b_run_expires_month approach
    #    Remove usage of "expires_this_month", "sum(...)=1", etc.

    usage = {}
    expiration_date = {}
    isValid = {}

    # (A) Create expiration_date

    for p in products:
        for r in range(MAX_RUNS):
            exp_date = model.NewIntVar(0, bigM, f"exp_{p}_{r}")
            # Shelf life in days = SHELF_LIFE * DAYS_PER_MONTH
            model.Add(exp_date == finish_time[(p, r)] + SHELF_LIFE * DAYS_PER_MONTH)
            expiration_date[(p, r)] = exp_date

    # (B) Create usage variables for partial allocation across months
    for p in products:
        for r in range(MAX_RUNS):
            for m in range(1, TOTAL_MONTHS + 1):
                usage[(p, r, m)] = model.NewIntVar(0, bigM, f"usage_{p}_{r}_m{m}")

    # New: link usage to a boolean that says "this run actually supplies month m"
    supplies_month = {}
    for p in products:
        for r in range(MAX_RUNS):
            for m in range(1, TOTAL_MONTHS+1):
                sm = model.NewBoolVar(f"supplies_{p}_{r}_m{m}")
                supplies_month[(p,r,m)] = sm
                # If any usage > 0 then sm=1, else sm=0
                model.Add(usage[(p, r, m)] > 0).OnlyEnforceIf(sm)
                model.Add(usage[(p, r, m)] == 0).OnlyEnforceIf(sm.Not())
                # And enforce the no‐spill constraint:
                month_end = m * DAYS_PER_MONTH
                model.Add(finish_time[(p, r)] <= month_end).OnlyEnforceIf(sm)

    # (C) Link total usage to produced_protein_int
    for p in products:
        for r in range(MAX_RUNS):
            model.Add(
                sum(usage[(p, r, m)] for m in range(1, TOTAL_MONTHS + 1))
                <= produced_protein_int[(p, r)]
            )

    # (D) Demand coverage: sum usage across all runs in month m >= demand
    for p in products:
        for m in range(1, TOTAL_MONTHS + 1):
            model.Add(
                sum(usage[(p, r, m)] for r in range(MAX_RUNS))
                >= int(math.ceil(demand[p].get(m, 0)))
            )

    serves = {}  # will index (product,run,month) → Bool
    for p in products:
        for r in range(MAX_RUNS):
            for m in range(1, TOTAL_MONTHS+1):
                b = model.NewBoolVar(f"serves_{p}_{r}_m{m}")
                serves[(p,r,m)] = b

                # if we actually allocate any usage to month m, serves==1
                model.Add(usage[(p,r,m)] >= 1).OnlyEnforceIf(b)
                model.Add(usage[(p,r,m)] == 0).OnlyEnforceIf(b.Not())

    # (E) isValid[(p, r, m)] => run r can supply product p in month m
    for p in products:
        for r in range(MAX_RUNS):
            for m in range(1, TOTAL_MONTHS + 1):
                isValid[(p, r, m)] = model.NewBoolVar(f"isValid_{p}_{r}_m{m}")

    # Link isValid to day-based shelf life:
    for p in products:
        for r in range(MAX_RUNS):
            F = finish_time[(p, r)]  # day production finishes
            E = expiration_date[(p, r)]
            for m in range(1, TOTAL_MONTHS + 1):
                month_start = (30 * (m - 1))
                month_end = (30 * m) - 1
                valid = isValid[(p, r, m)]

                # If valid=1 => run finishes on/before month_end AND not expired before month_start
                model.Add(F <= month_end).OnlyEnforceIf(valid)
                model.Add(E > month_start).OnlyEnforceIf(valid)

                # If valid=0 => either finishes after the month ends OR expires before the month starts
                # We can do big-M reification, or simpler direct constraints:
                # model.Add(F > month_end).OnlyEnforceIf(valid.Not())
                # model.Add(E <= month_start).OnlyEnforceIf(valid.Not())
                # If you want "OR" logic, you'd need an extra bool.
                # For simplicity, use F>month_end as the main contradiction.

    # Force usage to 0 if not valid
    for p in products:
        for r in range(MAX_RUNS):
            for m in range(1, TOTAL_MONTHS + 1):
                model.Add(usage[(p, r, m)] <= bigM * isValid[(p, r, m)])
                
    # somewhere after you’ve built `isValid[(p,r,m)]` and `finish_time[(p,r)]`:
    earliness = {}
    for p in products:
        for r in range(MAX_RUNS):
            for m in range(1, TOTAL_MONTHS+1):
                # only care when this run actually supplies month m
                var = model.NewIntVar(0, bigM, f"earliness_{p}_{r}_m{m}")
                earliness[(p,r,m)] = var

                month_end = m * DAYS_PER_MONTH  # e.g. if DAYS_PER_MONTH=30, month_end = 30, 60, 90, …
                # 1) If run IS valid for month m, earliness >= (month_end − finish_time)
                model.Add(earliness[(p, r, m)] 
                        == month_end - finish_time[(p, r)]) \
                    .OnlyEnforceIf(serves[(p, r, m)])
                model.Add(earliness[(p, r, m)] == 0) \
                    .OnlyEnforceIf(serves[(p, r, m)].Not())

    for p in products:
        for r in range(MAX_RUNS):
            for m in range(1, TOTAL_MONTHS+1):
                month_start = (m - 1) * DAYS_PER_MONTH # e.g. 1, 31, 61, …
                month_end = m * DAYS_PER_MONTH - 1 # e.g. 30, 60, 90, …
                # If this run actually supplies month m, then:
                #   finish_time >= month_end - SLACK
                #   finish_time <= month_end
                # model.Add(finish_time[(p,r)] >= month_start).OnlyEnforceIf(serves[(p,r,m)])
                model.Add(finish_time[(p,r)] <= month_end)\
                    .OnlyEnforceIf(serves[(p,r,m)])

    # 2) DEFINE MONTH-TO-MONTH INVENTORY
    inventory = {}
    for p in products:
        for m in range(1, TOTAL_MONTHS + 1):
            inventory[(p, m)] = model.NewIntVar(0, bigM, f"Inventory_{p}_m{m}")

    # -- NEW CODE: Set inventory in month 1 to existing stock plus first production minus demand
    # If you want EXACT month 0 as your initial inventory, do:
    # inventory_month0 = {}
    # for p in products:
    #     # create an IntVar for inventory at 'month 0'
    #     inventory_month0[p] = model.NewIntVar(0, bigM, f"Inventory_{p}_m0")
    #     # set it to the existing stock:
    #     model.Add(inventory_month0[p] == products_inventory_protein[f"{p}"])

    # We interpret "monthly production" as the sum of usage in that month
    # Because usage = how much product is actually allocated to month m
    monthly_prod = {}
    for p in products:
        for m in range(1, TOTAL_MONTHS + 1):
            monthly_prod[(p, m)] = model.NewIntVar(0, bigM, f"monthly_prod_{p}_m{m}")
            model.Add(
                monthly_prod[(p, m)] == sum(usage[(p, r, m)] for r in range(MAX_RUNS))
            )

    # Demand is monthly_demand
    monthly_demand = {}
    for p in products:
        for m in range(1, TOTAL_MONTHS + 1):
            monthly_demand[p, m] = int(math.ceil(demand[p].get(m, 0)))

    # 3) INVENTORY FLOW CONSTRAINTS
    # Inv_{p,m} = Inv_{p,m-1} + monthly_prod[p,m] - monthly_demand[p,m]
    # --- INVENTORY WITH INITIAL STOCK DRIVES DEMAND COVERAGE ---
    inventory = {}
    for p in products:
        for m in range(1, TOTAL_MONTHS+1):
            inventory[(p, m)] = model.NewIntVar(0, bigM, f"inv_{p}_m{m}")

    # month 1: start with existing stock + any usage in month 1
    for p in products:
        model.Add(
            inventory[(p, 1)]
            == products_inventory_protein[p]
            + sum(usage[(p, r, 1)] for r in range(MAX_RUNS))
            - int(math.ceil(demand[p].get(1, 0)))
        )
        # months 2…TOTAL_MONTHS
        for m in range(2, TOTAL_MONTHS+1):
            model.Add(
                inventory[(p, m)]
                == inventory[(p, m-1)]
                + sum(usage[(p, r, m)] for r in range(MAX_RUNS))
                - int(math.ceil(demand[p].get(m, 0)))
            )
        # inventory can never go negative
        for m in range(1, TOTAL_MONTHS+1):
            model.Add(inventory[(p, m)] >= 0)

    
    # 1) sum up all earliness…
    total_earliness = model.NewIntVar(0, DAYS_PER_MONTH*len(earliness), "total_earliness")
    model.Add(total_earliness == sum(earliness.values()))

    # pre-compute line volumes (liters → grams):
    line_capacity = {
        (p, l): int(line_final_vol[(p, l)] * product_factor[p] / 1000.0)
        for p in products
        for l in product_lines[p]
    }

    # build a linear expression for “total run capacity”:
    cap_penalty = []
    for p in products:
        for r in range(MAX_RUNS):
            for l in product_lines[p]:
                cap_penalty.append(
                    line_capacity[(p, l)] * use_line[(p, r, l)]
                )



    # e.g. α=1000 to give primary weight to earliness, β=1 to break ties by fewer runs
    a = 3
    b = 2
    c = 1 # tiny weight compared to your a/b

    model.Minimize(
        a*total_earliness +
        b*sum(activate_run.values()) +
        c*sum(cap_penalty)
    )
    
    # obj = model.NewIntVar(0, bigM, "obj")
    # obj2 = model.NewIntVar(0, bigM, "obj2")
    # obj3 = model.NewIntVar(0, bigM, "obj3")

    # model.Add(obj == a * total_earliness + b * sum(activate_run.values()))
    # model.Add(obj == a * total_earliness)
    # model.Add(obj3 == c * sum(cap_penalty))
    # model.Add(obj2 == b * sum(activate_run.values()))
    # model.Minimize(obj)
    # model.Minimize(obj3)
    # model.Minimize(obj2)

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 200
    solver.parameters.cp_model_presolve = True  # Enable fast presolving to reduce model size
    solver.parameters.cp_model_probing_level = 2    # 0=off, 1=light, 2=strengthened
    solver.parameters.symmetry_level = 3  # Enables symmetry breaking during preprocessing
    solver.parameters.log_search_progress = True
    solver.parameters.num_search_workers = 6
    # solver.parameters.stop_after_first_solution = True
    
    status = solver.Solve(model)
    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print("No feasible solution.")
        return [], {}

    inventory_solution = {}
    for p in products:
        inventory_solution[p] = {}
        for m in range(1, TOTAL_MONTHS + 1):
            # Retrieve the value assigned by the solver to the inventory variable for product p in month m.
            inv_value = solver.Value(inventory[(p, m)])
            inventory_solution[p][m] = inv_value
            print(f"Product: {p}, Month: {m}, Inventory: {inv_value}, production: {solver.Value(monthly_prod[(p, m)])}, demand: {monthly_demand[p, m]}")
            
    # 7) Build final plan (updated for partial usage / Scenario B)
    final_plan = []
    for p in products:
        for r in range(MAX_RUNS):
            if solver.Value(activate_run[(p, r)]) == 0:
                continue

            # Check if the run is valid in at least one month.
            valid_run = False
            for m in range(1, TOTAL_MONTHS + 1):
                if solver.Value(isValid[(p, r, m)]) == 1:
                    valid_run = True
                    break
            if not valid_run:
                continue

            # Get run information
            fday = solver.Value(finish_time[(p, r)])
            exp_day = solver.Value(expiration_date[(p, r)])
            finish_date_str = day_to_date(fday)
            exp_date_str = day_to_date(exp_day)

            # Instead of assigning a unique production_month,
            # accumulate the usage (i.e. how much production is allocated) per month.
            monthly_usage = {}
            for m in range(1, TOTAL_MONTHS + 1):
                usage_val = solver.Value(usage[(p, r, m)])
                if usage_val > 0:
                    monthly_usage[m] = usage_val

            # Determine which production line was used:
            used_line_id = None
            for l_id in product_lines[p]:
                if solver.Value(use_line[(p, r, l_id)]) == 1:
                    used_line_id = l_id
                    break

            # Production quantity details
            litv = solver.Value(produced_liters[(p, r)])
            produced_f = (litv * product_factor[p]) / 1000.0

            # Gather the stage details (same as before)
            br_stages = []
            if used_line_id is not None:
                # Thawing stage.
                thaw_stage = {
                    "stage": "CellThawing & SF",
                    "start_day": solver.Value(stage_start[(p, r, used_line_id, 0)]),
                    "end_day": solver.Value(stage_end[(p, r, used_line_id, 0)]),
                    "start_date": day_to_date(
                        solver.Value(stage_start[(p, r, used_line_id, 0)])
                    ),
                    "end_date": day_to_date(
                        solver.Value(stage_end[(p, r, used_line_id, 0)])
                    ),
                }
                br_stages.append(thaw_stage)
                l_conf = product_lines[p][used_line_id]
                br_names = list(l_conf["BRs"].keys())
                for i, brn in enumerate(br_names):
                    stage_key = i + 1
                    s_val = solver.Value(stage_start[(p, r, used_line_id, stage_key)])
                    e_val = solver.Value(stage_end[(p, r, used_line_id, stage_key)])
                    stage_dict = {
                        "stage": brn,
                        "start_day": s_val,
                        "end_day": e_val,
                        "start_date": day_to_date(s_val),
                        "end_date": day_to_date(e_val),
                    }
                    br_stages.append(stage_dict)
                    if (p, r, used_line_id, stage_key) in harvest_vars:
                        harv_s = solver.Value(
                            harvest_vars[(p, r, used_line_id, stage_key)][0]
                        )
                        harv_e = solver.Value(
                            harvest_vars[(p, r, used_line_id, stage_key)][1]
                        )
                        harvest_dict = {
                            "stage": f"Harvest {brn}",
                            "start_day": harv_s,
                            "end_day": harv_e,
                            "start_date": day_to_date(harv_s),
                            "end_date": day_to_date(harv_e),
                        }
                        br_stages.append(harvest_dict)
                    if (p, r, used_line_id, stage_key) in hold_vars:
                        hold_s = solver.Value(
                            hold_vars[(p, r, used_line_id, stage_key)][0]
                        )
                        hold_e = solver.Value(
                            hold_vars[(p, r, used_line_id, stage_key)][1]
                        )
                        hold_dict = {
                            "stage": f"Hold {brn}",
                            "start_day": hold_s,
                            "end_day": hold_e,
                            "start_date": day_to_date(hold_s),
                            "end_date": day_to_date(hold_e),
                        }
                        br_stages.append(hold_dict)
                    # Mab stages and Follow-Up stages
                    mab_idx = 1
                    while (p, r, used_line_id, stage_key, mab_idx) in mab_vars:
                        mab_st = solver.Value(
                            mab_vars[(p, r, used_line_id, stage_key, mab_idx)][0] + 1
                        )
                        mab_e = solver.Value(
                            mab_vars[(p, r, used_line_id, stage_key, mab_idx)][1] + 1
                        )
                        mab_dict = {
                            "stage": f"Mab {mab_idx} {brn}",
                            "start_day": mab_st,
                            "end_day": mab_e,
                            "start_date": day_to_date(mab_st),
                            "end_date": day_to_date(mab_e),
                        }
                        br_stages.append(mab_dict)
                        mab_idx += 1
                    # Insert a similar loop for the SS's that you stored under mab_vars with an offset like 1000+sss_idx
                    sss_idx = 1001
                    while (p, r, used_line_id, stage_key, sss_idx) in mab_vars:
                        sss_st = solver.Value(
                            mab_vars[(p, r, used_line_id, stage_key, sss_idx)][0] + 1
                        )
                        sss_e = solver.Value(
                            mab_vars[(p, r, used_line_id, stage_key, sss_idx)][1] + 1
                        )
                        sss_dict = {
                            "stage": f"SS {sss_idx - 1000} {brn}",
                            "start_day": sss_st,
                            "end_day": sss_e,
                            "start_date": day_to_date(sss_st),
                            "end_date": day_to_date(sss_e),
                        }
                        br_stages.append(sss_dict)
                        sss_idx += 1

                    fu_key = f"Follow_Up_{brn}"
                    if fu_key in l_conf:
                        fu_dict = l_conf[fu_key]
                        for fu_name, fu_duration in fu_dict.items():
                            fu_var_key = (p, r, used_line_id, stage_key, fu_name)
                            if fu_var_key in fu_vars:
                                fu_st = solver.Value(fu_vars[fu_var_key][0])
                                fu_e = solver.Value(fu_vars[fu_var_key][1])
                                fu_dict_out = {
                                    "stage": f"FU {fu_name}",
                                    "start_day": fu_st,
                                    "end_day": fu_e,
                                    "start_date": day_to_date(fu_st),
                                    "end_date": day_to_date(fu_e),
                                }
                                br_stages.append(fu_dict_out)

            # Determine a release day:
            release_day = None
            for stage in br_stages:
                if "Release" in stage["stage"]:
                    release_day = stage["end_day"]
                    break
            if release_day is None:
                release_day = fday

            # Build the final plan dictionary (no longer using a single production month)
            final_plan.append(
                {
                    "product": p,
                    "run_index": r,
                    "line_used": used_line_id,
                    "finish_day": fday,
                    "finish_date": finish_date_str,
                    "monthly_usage": monthly_usage,  # new field with a month->usage mapping
                    "liters": litv,
                    "production_month": None,
                    "produced_protein": produced_f,
                    "br_stages": br_stages,
                    "release_day": release_day,
                    "expiration_date": exp_day,
                    "expiration_date_str": exp_date_str,
                }
            )

    # Optionally, sort the final plan (you may sort by product name, or use another criterion)
    final_plan.sort(key=lambda x: (x["product"]))

    # Instead of reading the model’s inventory variables (which might be driven to 0)
    # we compute the cumulative inventory from the solved usage values.
    inv_traj: dict[str, dict[int, int]] = {}
    product_initial_stock = {}
    for p in products:
        inv_traj[p] = {}
        # Instead of 0, set current_inv to the existing stock for p
        # e.g. if your existing stock is stored in a dict existing_stock[p]
        # or if you store it as inventory_month0 in the solver, you can read that value here.
        initial_stock = products_inventory_protein[f"{p}"]  # or solver.Value(inventory_month0[p]) if that is an IntVar
        product_initial_stock[p] = initial_stock
        current_inv = initial_stock
        for m in range(1, TOTAL_MONTHS + 1):
            # Sum the production allocated to product p in period m over all runs.
            # Here, usage[(p, r, m)] is the CP variable from which we get the solver’s value.
            monthly_production = sum(
                solver.Value(usage[(p, r, m)]) for r in range(MAX_RUNS)
            )
            monthly_demand = int(math.ceil(demand[p].get(m, 0)))
            # Cumulatively update inventory:
            # current_inv = previous_inv + production in m - demand in m
            current_inv = current_inv + monthly_production - monthly_demand
            inv_traj[p][m] = current_inv
    print("Inventory Start => ",inv_traj)

    return final_plan, inv_traj, product_initial_stock

def run_feasibility_model(data: dict[str, dict], demand: dict[str, dict]) -> dict[str, float]:
    """
    Builds a simplified CP-SAT model that determines the maximum production capacity
    of each product (ignoring demand constraints) in the planning horizon.
    Returns a dictionary of feasible capacity for each product.
    """
    model = cp_model.CpModel()
    # Use a smaller number of runs for the feasibility phase if desired:
    FEAS_MAX_RUNS = 100

    # We reuse some basic configuration parts (for example product_lines, factors, etc.)
    all_prods = list(data["Common_Lines"].keys())
    products = [p for p in all_prods if p in demand]
    product_lines = {}
    product_factor = {}
    base_configs = {}
    for p in products:
        conf_list = data[p]
        base_conf = conf_list[0]
        base_configs[p] = base_conf
        lines_conf = conf_list[1]
        factor = base_conf.get("Protein_per_1000L_BR", 0.0)
        product_factor[p] = factor
        if "lines" in lines_conf:
            lines_list = lines_conf["lines"]
        else:
            lines_list = lines_conf.get("RC", [])
        active_lines = {}
        for li in lines_list:
            if li.get("status") == "active":
                active_lines[li["id"]] = li
        product_lines[p] = active_lines

    # Create dummy decision variables for production runs. (We mimic the main model without the demand constraints)
    produced_protein_int = {}
    finish_time = {}
    # For each product and each run, create a variable for produced protein.
    for p in products:
        for r in range(FEAS_MAX_RUNS):
            # You can assume that a run, if activated, produces what the base configuration indicates.
            # For simplicity, let’s assume each run produces at most 1000 units (scaled factor) and 
            # we let the production be an IntVar.
            produced_protein_int[(p, r)] = model.NewIntVar(0, 10_000, f"prod_{p}_{r}")
            # Also create a finish time variable (our objective here is to maximize total produced protein)
            finish_time[(p, r)] = model.NewIntVar(0, 50000, f"finish_{p}_{r}")
            # (In a full model you’d add production chain constraints.)
            # Here we set an artificial relation for a used run:
            model.Add(produced_protein_int[(p, r)] >= 0)

    # For the feasibility phase, simply maximize total production summed over runs for each product.
    total_production = {}
    for p in products:
        total_production[p] = model.NewIntVar(0, 1_000_000, f"total_production_{p}")
        model.Add(total_production[p] == sum(produced_protein_int[(p, r)] for r in range(FEAS_MAX_RUNS)))
    # Our objective: maximize the total production for each product
    model.Maximize(sum(total_production[p] for p in products))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
    status = solver.Solve(model)
    feasible_capacity = {}
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        for p in products:
            feasible_capacity[p] = solver.Value(total_production[p])
    else:
        print("Feasibility model could not find a solution.")
        for p in products:
            feasible_capacity[p] = 0
    return feasible_capacity

def compute_monthly_demand_differences(original_demand: dict[str, dict], model_capacity: dict[str, dict[int, int]]) -> dict[str, dict[int, int]]:
    """
    Compares each month's demand from original_demand with the inventory model's capacity (model_capacity)
    and returns, for each product and month, the difference.
    model_capacity is assumed to be a dictionary in which model_capacity[p][m] is the total produced 
    and allocated production (available) for product p in month m.
    Returns a nested dictionary { product: {month: difference, ...}, ... }.
    """
    monthly_diff = {}
    for p, months in original_demand.items():
        monthly_diff[p] = {}
        
        # Check if model_capacity[p] is a dictionary (month-wise breakdown)
        if isinstance(model_capacity.get(p), dict):
            # Correct case: model_capacity[p] is a dictionary with month keys
            for m, demand in months.items():
                capacity = model_capacity[p].get(m, 0)  # Get the capacity for month m
                monthly_diff[p][m] = demand - capacity  # if positive, there is a shortfall
        else:
            # If model_capacity[p] is not a dictionary, it could be a total capacity
            total_capacity = model_capacity.get(p, 0)
            for m, demand in months.items():
                # Divide the total capacity equally across months or use another method
                # Here, we assume even distribution of total_capacity across months
                monthly_capacity = total_capacity / len(months)  # Simple even distribution
                monthly_diff[p][m] = demand - monthly_capacity  # Demand minus the computed monthly capacity

    return monthly_diff

############################################################################################################################


# --- Compute Inventory per Period Considering Shelf Life ---
def compute_inventory_by_period(final_plan, max_period, products_inventory_protein):
    """
    For each production run in final_plan, compute the available (non–expired) protein
    at the end of each period, using whole–unit expiration.

    Each period m covers day offsets from 30*(m-1) to 30*m-1.
    The available amount for a run in period m is computed as follows:
       - If the run has not finished by the period end or is already expired by the period start, available = 0.
       - Otherwise, compute the run's base leftover (produced protein minus total allocated usage up to and including period m).
       - If the expiration day falls within the current period (i.e. exp_day <= period_end),
         then the run’s entire remaining amount is expired in that period (available = 0).
       - Otherwise, the entire base leftover is carried over as available.
    The results are summed by product and by period.
    """
    inv_by_period = {}
    # Loop over production runs.
    for run in final_plan:
        prod = run["product"]
        produced = run["produced_protein"]
        usage = run.get("monthly_usage", {})  # e.g. {1: 2481, 2: 826, ...}
        finish = run["finish_day"]  # day offset when the run finished
        exp_day = run[
            "expiration_date"
        ]  # computed as finish_day + SHELF_LIFE * DAYS_PER_MONTH
        # Loop over each period.
        for m in range(1, max_period + 1):
            if m == 1:
                produced += products_inventory_protein.get(prod, 0)
            # Define period boundaries.
            period_start = (m - 1) * 30
            period_end = m * 30 - 1
            # Initialize available for this run in period m.
            available = 0.0
            # Only if the run has finished (finish <= period_end) and is not expired
            # before the period starts (exp_day > period_start) do we consider leftover.
            if finish <= period_end and exp_day > period_start:
                # Compute total consumption allocated from this run up to period m.
                consumed = sum(usage.get(i, 0) for i in range(1, m + 1))
                base_leftover = max(produced - consumed, 0)
                # If the run expires within the current period, remove the entire leftover.
                if exp_day <= period_end:
                    available = 0.0
                else:
                    available = base_leftover
            # Sum up the available production for the product in period m.
            inv_by_period.setdefault(prod, {})
            inv_by_period[prod][m] = inv_by_period[prod].get(m, 0) + available
    return inv_by_period


# --- Compute "New Production" per Period ---
def compute_new_prod(final_plan, max_period):
    """
    For each run, if its finish day falls within a period, attribute its total produced protein
    as “new production” for that period. Returns a dictionary:
        { product: { period: total produced } }.
    """
    new_prod = {}
    for run in final_plan:
        prod = run["product"]
        produced = run["produced_protein"]
        finish = run["finish_day"]
        # If finish is negative, assume production is counted in period 1.
        period = 1 if finish < 0 else int(finish // 30) + 1
        if period <= max_period:
            new_prod.setdefault(prod, {}).setdefault(period, 0)
            new_prod[prod][period] += produced
    return new_prod


# --- Production Runs Detail Report ---
def print_production_runs_detail(final_plan) -> str:
    """
    Print a table showing details of each production run:
      - Run index, production line,
      - Finish date and day offset,
      - Expiration date,
      - Produced protein,
      - The “leftover” (i.e. produced minus allocated usage),
      - And a summary of the monthly usage allocation.
    """
    lines = []
    lines.append("=== Production Runs Detail ===\n")
    print("\n=== Production Runs Detail ===")
    runs_by_product = {}
    for run in final_plan:
        prod = run["product"]
        runs_by_product.setdefault(prod, []).append(run)

    for prod in sorted(runs_by_product.keys()):
        print(f"Product: {prod}")
        lines.append(f"Product: {prod}")
        header = f"{'Run':<4} {'Line':<6} {'Finish Date':<12} {'Finish Day':>10} {'Exp Date':<12} {'Protein':>10} {'Leftover':>10} {'Monthly Usage':>30}"
        print(header)
        print("-" * len(header))
        lines.append(header)
        lines.append("-" * len(header))
        sorted_runs = sorted(
            runs_by_product[prod],
            key=lambda x: (
                x["finish_day"],
                sum(x["monthly_usage"].values()) if x["monthly_usage"] else 0,
            ),
        )
        for run in sorted_runs:
            run_idx = run.get("run_index", "N/A")
            line_used = run.get("line_used", "N/A")
            finish_day = run.get("finish_day", 0)
            finish_date = run.get("finish_date", "N/A")
            exp_date = run.get("expiration_date_str", "N/A")
            produced_protein = run.get("produced_protein", 0)
            usage = run.get("monthly_usage", {})
            total_consumed = sum(usage.values())
            leftover = produced_protein - total_consumed
            usage_str = (
                ", ".join(f"{k}:{v}" for k, v in usage.items()) if usage else "None"
            )
            print(
                f"{run_idx:<4} {line_used!s:<6} {finish_date:<12} {finish_day:>10} {exp_date:<12} {produced_protein:>10.2f} {leftover:>10.2f} {usage_str:>30}"
            )
            lines.append(
                f"{run_idx:<4} {line_used!s:<6} {finish_date:<12} {finish_day:>10} {exp_date:<12} {produced_protein:>10.2f} {leftover:>10.2f} {usage_str:>30}"
            )
            lines.append("")
    return "\n".join(lines)

# --- Aggregated Calendar-Based Inventory Summary ---
def print_aggregated_inventory(final_plan, demand, max_period, products_inventory_protein) -> list[dict, str]:
    """
    Print an aggregated, calendar-based inventory table per product.
    For each period (calculated as 30–day blocks using day_to_date),
    the table shows:
      - Period label (start and end dates)
      - Demand (rounded up)
      - New production that becomes available (from runs finishing in that period)
      - Inventory at the start of the period (i.e. leftover from previous period)
      - Inventory at the end of the period (aggregated over all production runs, accounting for shelf life)
      - A balance (Inv Start + New Prod – Demand) with surplus/shortage annotation,
      - And the leftover (which here is the same as Inv End).
    """
    lines = []
    Inventory_Chart_Data = {}
    # Assume new_prod is computed as before:
    new_prod = compute_new_prod(final_plan, max_period)
    inv_by_period = compute_inventory_by_period(final_plan, max_period, products_inventory_protein)
    print("\n=== Aggregated Calendar-Based Inventory Summary ===")
    lines.append("\n=== Aggregated Calendar-Based Inventory Summary ===\n")
    
    for prod in sorted(demand.keys()):
        Inventory_Chart_Data[prod] = {}
        print(f"\nProduct: {prod}")
        lines.append(f"Product: {prod}")
        header = f"{'Period (Date Range)':<30} {'Demand':>10} {'New Prod':>10} {'Inv Start':>10} {'Inv End':>10} {'Balance':>20} {'Leftover':>10} {'Expired':>10}"
        print(header)
        print("-" * len(header))
        lines.append(header)
        lines.append("-" * len(header))
        for m in range(1, max_period + 1):
            period_start_date = day_to_date((m - 1) * 30)
            period_end_date = day_to_date(m * 30 - 1)
            period_label = f"{period_start_date} - {period_end_date}"
            dem_val = int(math.ceil(demand[prod].get(m, 0)))
            np_val = new_prod.get(prod, {}).get(m, 0)
            inv_start = inv_by_period[prod].get(m - 1, 0)
            inv_end = inv_by_period[prod].get(m, 0)
            balance = (inv_start + np_val) - dem_val
            balance_text = (
                f"Surplus: {balance:.2f}"
                if balance >= 0
                else f"Shortage: {abs(balance):.2f}"
            )
            Inventory_Chart_Data[prod][m] = inv_end
            # With the new rule, expired amount is the difference between the theoretical balance (if no expiration)
            # and the actual inventory carried (which in an expiration period becomes 0 for that run).
            expired = max((inv_start + np_val - dem_val) - inv_end, 0)
            print(
                f"{period_label:<30} {dem_val:>10} {np_val:>10.2f} {inv_start:>10.2f} {inv_end:>10.2f} {balance_text:>20} {inv_end:>10.2f} {expired:>10.2f}"
            )
            lines.append(
                f"{period_label:<30} {dem_val:>10} {np_val:>10.2f} {inv_start:>10.2f} {inv_end:>10.2f} {balance_text:>20} {inv_end:>10.2f} {expired:>10.2f}"
            )
    print("\n=== End of Inventory Summary ===")
    
    lines.append("\n=== End of Inventory Summary ===")
    lines = "\n".join(lines)
    
    return [Inventory_Chart_Data, lines]

def print_plan_with_preparation_stages(updated_plan) -> str:
    """
    Print the plan with any newly inserted "Prepare" stages before the main BioReactor stages.
    Assumes each run in updated_plan has:
      - 'product'
      - 'run_index'
      - 'line_used'
      - 'finish_day'
      - 'finish_date'
      - 'br_stages' (a list of stages, each with 'stage', 'start_day', 'end_day', 'start_date', 'end_date')
    """


    lines: list[str] = []
    runs_by_product: dict[str, list] = {}

    for run in updated_plan:
        prod = run["product"]
        runs_by_product.setdefault(prod, []).append(run)

    lines.append("\n=== UPDATED PLAN WITH PREPARATION STAGES ===")
    print("\n=== UPDATED PLAN WITH PREPARATION STAGES ===")
    for prod in sorted(runs_by_product.keys()):
        print(f"\nProduct: {prod}")
        lines.append(f"\nProduct: {prod}")
        # Sort runs by finish_day for consistency
        sorted_runs = sorted(
            runs_by_product[prod], key=lambda x: x.get("finish_day", 0)
        )
        for run in sorted_runs:
            run_idx = run.get("run_index", "N/A")
            line_used = run.get("line_used", "N/A")
            finish_day = run.get("finish_day", 0)
            finish_date = run.get("finish_date", "N/A")
            produced_protein = run.get("produced_protein", 0)

            print(
                f"  Run={run_idx}, Line={line_used}, FinishDay={finish_day} ({finish_date}), "
                f"Protein={produced_protein:.2f}"
            )
            lines.append(
                f"  Run={run_idx}, Line={line_used}, FinishDay={finish_day} ({finish_date}), "
                f"Protein={produced_protein:.2f}"
            )

            # Print stages
            br_stages = run.get("br_stages", [])
            for stage in br_stages:
                st_name = stage.get("stage", "N/A")
                st_start_day = stage.get("start_day", "N/A")
                st_end_day = stage.get("end_day", "N/A")
                st_start_date = stage.get("start_date", "N/A")
                st_end_date = stage.get("end_date", "N/A")

                print(
                    indent(
                        f"- Stage={st_name}, "
                        f"StartDay=({st_start_day}), EndDay=({st_end_day}), "
                        f"StartDate=({st_start_date}), EndDate=({st_end_date})",
                        prefix="    ",
                    )
                )
                lines.append(
                    indent(
                        f"- Stage={st_name}, "
                        f"StartDay=({st_start_day}), EndDay=({st_end_day}), "
                        f"StartDate=({st_start_date}), EndDate=({st_end_date})",
                        prefix="    ",
                    )
                )
            lines.append("")
            print()  # blank line after each run
    return "\n".join(lines)


def add_bioreactor_preparation_stages(final_plan):
    """
    Post-process the final_plan to insert a preparation stage before each BioReactor stage
    (any stage whose name indicates a numeric volume).

    Rules:
      - If parse_volume(stage_name) >= 1000 => 5 days prep
      - Else => 3 days prep
      - The new "X Prepare" stage ends exactly when the real BR stage starts.

    This modifies only the final plan dictionary for reporting convenience
    (it does NOT update the solver constraints or the actual schedule).
    """
    import copy

    def parse_volume(br_name: str) -> float:
        """Extracts the leading number from the stage name (e.g., '25' or '2000-3')."""
        chunk = br_name.split("-")[0]  # e.g. "2000" from "2000-3"
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        return float(digits) if digits else 0.0

    def day_to_date(day_offset: int) -> str:
        """Convert a day offset to an ISO formatted date string. Adjust as needed to match your base date."""
        from datetime import date, timedelta

        base = date(2026, 1, 1)  # The base date in your system
        actual_date = base + timedelta(days=day_offset)
        return actual_date.isoformat()

    updated_plan = []
    for run in final_plan:
        # Make a shallow copy of the run dictionary so we don't mutate the original
        new_run = copy.copy(run)

        # We'll rebuild the br_stages list with the inserted "Prepare" stages
        new_br_stages = []
        for st in run.get("br_stages", []):
            st_name = st["stage"]
            # Check if this stage name has a numeric volume
            vol = parse_volume(st_name)
            if vol > 0:  # It's a BioReactor stage
                # Decide how many prep days
                prep_days = 5 if vol >= 1000 else 3

                # Insert a "Prepare" stage that ends exactly when this stage starts
                prep_start = st["start_day"] - prep_days
                prep_end = st["start_day"] - 1

                prep_stage = {
                    "stage": f"{st_name} Prepare",
                    "start_day": prep_start,
                    "end_day": prep_end,
                    "start_date": day_to_date(prep_start),
                    "end_date": day_to_date(prep_end),
                }
                new_br_stages.append(prep_stage)

            # Whether it's a BR stage or not, we then append the original stage
            new_br_stages.append(st)

        # Replace the old br_stages with the new list
        new_run["br_stages"] = new_br_stages
        updated_plan.append(new_run)

    return updated_plan


def list_of_dicts_to_pdf(data, filename):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # Set starting position
    y_position = height - 40

    # Write each dictionary in the list to the PDF
    for index, dictionary in enumerate(data):
        if y_position < 40:  # Check if we need to create a new page
            c.showPage()
            y_position = height - 40  # Reset position for new page

        c.drawString(100, y_position, f"Record {index + 1}:")
        y_position -= 20  # Move down for the next line

        for key, value in dictionary.items():
            c.drawString(120, y_position, f"{key}: {value}")
            y_position -= 20  # Move down for the next line

    c.save()

def Output_Printers(final_plan: list[dict], inv_traj: dict[str, dict], demand, products_inventory_protein):
    
    updated_plan = add_bioreactor_preparation_stages(final_plan)
    lines_detail = print_plan_with_preparation_stages(updated_plan)
    #################################################################################################

    #################################################################################################
    """
    Print a complete report combining production run details and an aggregated, calendar-based inventory summary.
    
    The planning horizon is extended to cover all periods until the last expiration.
    For each product, the report shows detailed run-level production information and then an inventory summary
    that accounts for shelf life (with fractional availability in the period when production expires).
    """
    # Determine the maximum period to report.
    # Compute the maximum expiration day among all runs and convert it into a period.
    if final_plan:
        max_exp_day = max(run["expiration_date"] for run in final_plan)
        max_period = max(TOTAL_MONTHS, int(max_exp_day // 30) + 1)
    else:
        max_period = TOTAL_MONTHS

    
    # Convert list of dictionaries to PDF
    list_of_dicts_to_pdf(final_plan, "E:\Sherkat_DeepSpring_projects\Aryogen_Planning\Data\output.pdf")
    
    # # Section 1: Detailed Production Runs.
    # print_production_runs_detail(final_plan)

    # # Section 2: Aggregated Calendar-Based Inventory Summary.
    # print_aggregated_inventory(final_plan, demand, max_period, products_inventory_protein)
    

    # Section 1: Detailed Production Runs
    lines = print_production_runs_detail(final_plan)

    # Section 2: Aggregated Calendar-Based Inventory Summary
    front_payload = print_aggregated_inventory(final_plan, demand, max_period, products_inventory_protein)
    
    #################################################################################################

    return front_payload, lines, lines_detail

# --- MODIFIED CODE in main() to handle AryoSeven_RC with a separate planner ---
def main(total_products_protein_per_month, products_inventory_protein, payload, export_stock_protein, sales_stock_protein):
    print("run with extended schedule (can start before day 0)...")
    with open("E:\\Sherkat_DeepSpring_projects\\PharmaAI\\Data\\Lines.json", "r") as f:
        data = json.load(f)
    
    base_date = parse_base_date(payload.selectedDate)
    set_base_date_for_planning(base_date)
    set_total_months(payload.monthsCount)

    demand_Export: dict[str, dict[int, float]] = {}
    demand_Sales:  dict[str, dict[int, float]] = {}

    # EXPORT
    for prdct, month_map in export_stock_protein.items():
        for m, grams in month_map.items():
            demand_Export.setdefault(prdct, {}).setdefault(m, 0.0)
            demand_Export[prdct][m] += grams

    # SALES
    for prdct, month_map in sales_stock_protein.items():
        for m, grams in month_map.items():
            demand_Sales.setdefault(prdct, {}).setdefault(m, 0.0)
            demand_Sales[prdct][m] += grams

    print("Demand dict before distribution:\n", demand_Sales)
    print("Export dict before distribution:\n", demand_Export)
    
    # # Build the 'demand' dict as you do
    # demand_Export: dict[str, dict[int, float]] = {} # Initialize demand_Sales dictionary 
    # for key, val in export_stock_protein.items():
    #     product_part, idx_str = key.rsplit(" ", 1)
    #     m = int(idx_str)
    #     base_product = " ".join(product_part.split()[:-1]) or product_part
    #     demand_Export.setdefault(base_product, {})
    #     demand_Export[base_product][m] = demand_Export[base_product].get(m, 0.0) + float(val)

    # # Build the 'demand' dict as you do
    # demand_Sales: dict[str, dict[int, float]] = {} # Initialize demand_Sales dictionary 
    # for key, val in sales_stock_protein.items():
    #     product_part, idx_str = key.rsplit(" ", 1)
    #     m = int(idx_str)
    #     base_product = " ".join(product_part.split()[:-1]) or product_part
    #     demand_Sales.setdefault(base_product, {})
    #     demand_Sales[base_product][m] = demand_Sales[base_product].get(m, 0.0) + float(val)

    products = []
    # For demonstration, let's keep the logic that redistributes total demand_Sales equally across 12 months
    for product, monthly_demand in demand_Sales.items():
        products.append(product)
        for mm in range(1, TOTAL_MONTHS + 1):
            demand_Sales[product][mm] = (3 * demand_Sales[product][mm])
            demand_Sales[product][mm] += demand_Export.get(product, {}).get(mm, 0.0) 
    print("Demand dict after distribution:\n", demand_Sales)
            
    # Initialize a dictionary to track stock usage for each product and month
    stock_usage = {}  
    for p in products:
        stock_usage[p] = {}  # Initialize stock usage tracking for each product

        initial_stock_inventory = products_inventory_protein.get(p, 0)  # The initial stock for the product
        
        # Loop through each month to match stock usage with demand
        for m in range(1, TOTAL_MONTHS + 1):
            if initial_stock_inventory > 0:
                # If there is still initial stock available, use it to fulfill the demand
                demand_for_month = math.ceil(demand_Sales[p].get(m, 0))  # Get the demand for the month
                stock_used = min(initial_stock_inventory, demand_for_month)  # Use as much stock as possible to fulfill the demand
                stock_usage[p][m] = stock_used  # Track how much stock was used in this month
                
                if stock_usage[p][m] == demand_for_month:
                    demand_Sales[p][m] = 0  # If the demand is fully met, set it to 0
                elif stock_usage[p][m] < demand_for_month:
                    demand_Sales[p][m] -= stock_used
                    products_inventory_protein[p] = 0
                
                initial_stock_inventory -= stock_used  # Decrease the available stock
            else:
                pass

    
    # If AryoSeven_RC is in the demand, call the specialized planner
    final_plan_RC, inv_traj_RC = [], {}
    if "AryoSeven_RC" in demand_Sales:
        final_plan_RC, inv_traj_RC = build_schedule_for_AryoSevenRC(data, demand_Sales)

    # Now remove "AryoSeven_RC" from the demand_Sales dict so it doesn't go into the normal build_schedule_with_inventory
    if "AryoSeven_RC" in demand_Sales:
        del demand_Sales["AryoSeven_RC"]

    # Run the feasibility model to extract the maximum production capacities.
    feasible_capacity = run_feasibility_model(data, demand_Sales)
    print("Feasible production capacity per product:", feasible_capacity)

    # Compute the differences between original (or redistributed) demand and feasible capacity.
    demand_gap = compute_monthly_demand_differences(demand_Sales, feasible_capacity)
    print("Demand gaps (original demand - feasible capacity):", demand_gap)

    positive_demand_gaps = {}  # Dictionary to store products with positive gaps
    # Loop through the demand gaps and filter for positive gaps
    for product, monthly_gaps in demand_gap.items():
        positive_months = {}  # Store months with positive gaps for this product
        
        for month, gap in monthly_gaps.items():
            if gap > 0:  # If the gap is positive, store it in the positive_months dictionary
                positive_months[month] = gap
        
        if positive_months:  # Only add to the result if there are positive gaps for this product
            positive_demand_gaps[product] = positive_months

    # Now, print the positive demand gaps
    print("Products with positive gaps and their monthly differences:")
    for product, months in positive_demand_gaps.items():
        print(f"Product: {product}")
        for month, gap in months.items():
            print(f"  Month {month}: Gap = {gap:.2f}")
        print()  # New line between products


    # # Optionally, adjust the demand if required. For instance, scale down if gap is too high:
    # adjusted_demand = {}
    # for p in demand.keys():
    #     total_demand = sum(demand[p].values())
    #     capacity = feasible_capacity.get(p, total_demand)
    #     # Calculate the scaling factor, ensuring it is no greater than 1.0:
    #     scale_factor = min(1.0, capacity / total_demand) if total_demand > 0 else 1.0
    #     adjusted_demand[p] = {m: demand[p][m] * scale_factor for m in demand[p].keys()}
    # print("Adjusted demand:", adjusted_demand)
    
    # # Dictionary to hold the differences
    demand_differences = {}
    # # Compare the original demand with adjusted demand to calculate the differences
    # for product in demand:
    #     for month in demand[product]:
    #         original = demand[product][month]
    #         adjusted = adjusted_demand[product][month]
            
    #         # Calculate the difference if there's a reduction (positive value means reduction)
    #         difference = original - adjusted
    #         if difference > 0:  # Only store if there was a reduction
    #             if product not in demand_differences:
    #                 demand_differences[product] = {}
    #             demand_differences[product][month] = difference

    # Now, print the demand differences
    # print("Demand differences (reduced demand):")
    # for product, months in demand_differences.items():
    #     print(f"Product: {product}")
    #     for month, diff in months.items():
    #         print(f"  Month {month}: Difference = {diff}")
            
    # The rest of products (including AryoSeven_BR) go through the normal build_schedule_with_inventory
    final_plan, inv_traj, initial_stock = build_schedule_with_inventory(data, demand_Sales, products_inventory_protein, payload)

    if not final_plan:
        print(
            "No feasible total plan found with extended schedule. Possibly no runs were activated."
        )
        
    if not final_plan_RC and not final_plan:
        print(
            "No feasible plan found for AryoSeven_RC with extended schedule. Possibly no runs were activated."
        )

    # Combine results
    combined_plan = final_plan + final_plan_RC
    # Combine inventories
    for k, v in inv_traj_RC.items():
        inv_traj[k] = v

    
    front_payload, lines, lines_detail = Output_Printers(combined_plan, inv_traj, demand_Sales, products_inventory_protein)
    # or build your final payload from combined results
    
    if demand_differences == {}:
        demand_differences = "No reductions"
    # Create a payload to return
    payload = {
        "status": "OK",
        "final_plan": combined_plan,
        "inventory_trajectory": front_payload[0],
        "runs_detail": lines,
        "lines_detail": lines_detail,
        "detail_output": front_payload[1],
        "demand": demand_Sales,
        "demand_reduction": demand_differences,
        "feasible_capacity": demand_Sales,
        "initial_stock": initial_stock,
    }
    return payload


if __name__ == "__main__":
    main()