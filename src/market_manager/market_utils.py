from collections import defaultdict
from pyomo.environ import value
from datetime import datetime

def build_time_sets(total_days, DA_lookahead_hours, RT_resolution, RT_lookahead_periods):
    '''
    Build time sets for Day-Ahead (DA) and Real-Time (RT) markets.

    Args:
        total_days: Total number of days for which the time sets are to be created.
        DA_lookahead_hours: Number of hours to look ahead in the Day-Ahead market.
        RT_resolution: Resolution of the Real-Time market in minutes.
        RT_lookahead_periods: Number of periods to look ahead in the Real-Time market.

    Returns:
        DA_time_sets: A dictionary where keys are day indices and values are lists of hourly time indices.
        RT_time_sets: A dictionary where keys are day indices and values are lists of sub-hourly time indices.
    '''
    DA_time_sets = {}
    RT_time_sets = {}
    for day in range(total_days):
        # DA: Each day starts at hour 1, includes 24 hours plus lookahead
        DA_start = day * 24 + 1
        DA_end = DA_start + 24 + DA_lookahead_hours
        DA_time_sets[day] = list(range(DA_start, DA_end))

        # RT: Each day starts at sub-hourly index 1, includes all RT periods plus lookahead
        RT_start = day * 24 * 60/(RT_resolution) + 1
        RT_end = RT_start + (24) * 60/(RT_resolution) + 1
        RT_time_sets[day] = list(range(int(RT_start), int(RT_end)))
    return DA_time_sets, RT_time_sets

def fix_slow_units(source_model, target_model, data_resolution_minutes):
    data_per_hour = int(60 / data_resolution_minutes)
    for (_, source_gen_dict), (_, target_gen_dict) in zip(
        source_model.elements(element_type='generator', generator_type='thermal'),
        target_model.elements(element_type='generator', generator_type='thermal')
    ):
        if source_gen_dict["fast_start"] == True:
            continue
        hourly_commitment_values = source_gen_dict['commitment']["values"]
        target_gen_dict['fixed_commitment'] = {
            'data_type': 'time_series',
            'values': [v for v in hourly_commitment_values for _ in range(data_per_hour)]
        }
        # Fix regulation provider binary variables if present
        if 'regulation_provider' in source_gen_dict:
            hourly_reg_values = source_gen_dict['regulation_provider']["values"]
            target_gen_dict['fixed_regulation'] = {
                'data_type': 'time_series',
                'values': [v for v in hourly_reg_values for _ in range(data_per_hour)]
            }

def fix_all_binaries(source_model, target_model, data_resolution_minutes, pricing_problem=None):
    '''
    Fix binary variables from source model to target model by expanding hourly values to match target model's resolution.

    Args:
        source_model: The source model containing the binary variables to be fixed.
        target_model: The target model where the binary variables will be fixed.
        data_resolution_minutes: The resolution of the target model in minutes.
        pricing_problem: Optional; specify if the pricing problem is 'CHP'.

    Returns:
        None
    '''
    data_per_hour = int(60 / data_resolution_minutes)

    # Fix storage binary variables
    for (_, source_storage_dict), (_, target_storage_dict) in zip(
        source_model.elements(element_type='storage'),
        target_model.elements(element_type='storage')
    ):
        # Expand input/output binary variables to match target resolution
        hourly_input_binvars = source_storage_dict["binvar_input"]["values"]
        hourly_output_binvars = source_storage_dict["binvar_output"]["values"]
        target_storage_dict["ESSFixedInput"] = {
            "data_type": "time_series",
            "values": [v for v in hourly_input_binvars for _ in range(data_per_hour)]
        }
        target_storage_dict["ESSFixedOutput"] = {
            "data_type": "time_series",
            "values": [v for v in hourly_output_binvars for _ in range(data_per_hour)]
        }
        # For BESS and PHS, also fix ancillary service binary variables
        if target_storage_dict["storage_type"] in {"BESS", "PHS"}:
            for key in ["Reg", "SP", "NSP", "SUPP"]:
                hourly_AS_binvars = source_storage_dict[f"binvar_{key}"]["values"]
                target_storage_dict[f"ESSFixed{key}"] = {
                    "data_type": "time_series",
                    "values": [v for v in hourly_AS_binvars for _ in range(data_per_hour)]
                }
            # For PHS, fix additional mode/start binary variables
            if target_storage_dict["storage_type"] == "PHS":
                hourly_HSCmode_binvars = source_storage_dict["PHSConventionalMode"]["values"]
                target_storage_dict["PHSFixedConventionalMode"] = {
                    "data_type": "time_series",
                    "values": [v for v in hourly_HSCmode_binvars for _ in range(data_per_hour)]
                }
                phs_keys = [
                    ("PHSFixedGenMode", "Unit_GenMode"),
                    ("PHSFixedPumpMode", "Unit_PumpMode"),
                    ("PHSFixedGenStart", "Unit_GenStart"),
                    ("PHSFixedPumpStart", "Unit_PumpStart")
                ]
                for new_key, old_key in phs_keys:
                    target_storage_dict[new_key] = {}
                    for unit_key, unit_dict in source_storage_dict[old_key].items():
                        hourly_vals = unit_dict["values"]
                        if "Start" in new_key:
                            # For Start variables: [1,0,0,0,...] or [0,0,0,...]
                            expanded = [
                                1 if v == 1 and i == 0 else 0
                                for v in hourly_vals
                                for i in range(data_per_hour)
                            ]
                        else:
                            # For Mode variables: repeat full-hour value
                            expanded = [
                                v for v in hourly_vals for _ in range(data_per_hour)
                            ]
                        target_storage_dict[new_key][unit_key] = {
                            "data_type": "time_series",
                            "values": expanded
                        }

    # # If pricing problem is CHP, skip generator binaries
    # if pricing_problem == 'CHP':
    #     return
    # Fix generator binary variables
    for (_, source_gen_dict), (_, target_gen_dict) in zip(
        source_model.elements(element_type='generator', generator_type='thermal'),
        target_model.elements(element_type='generator', generator_type='thermal')
    ):
        hourly_commitment_values = source_gen_dict['commitment']["values"]
        target_gen_dict['fixed_commitment'] = {
            'data_type': 'time_series',
            'values': [v for v in hourly_commitment_values for _ in range(data_per_hour)]
        }
        # Fix regulation provider binary variables if present
        if 'regulation_provider' in source_gen_dict:
            hourly_reg_values = source_gen_dict['regulation_provider']["values"]
            target_gen_dict['fixed_regulation'] = {
                'data_type': 'time_series',
                'values': [v for v in hourly_reg_values for _ in range(data_per_hour)]
            }

def fix_penalties_egret(egret_model, penalty_data, scaling_factor):
    '''
    Fix penalty parameters in the Pyomo model based on provided penalty data.

    Args:
        pyomo_model: The Pyomo model where penalties will be fixed.
        penalty_data: A dictionary containing penalty values for various constraints.
    '''
    egret_model.data["system"]["load_mismatch_cost"] = penalty_data.get("Curtailment_penalty")*scaling_factor
    egret_model.data["system"]["reserve_shortfall_cost"] = penalty_data.get("DA_reserve_shortfall_penalty")*scaling_factor
    egret_model.data["system"]["regulation_penalty_price"] = penalty_data.get("Reg_shortfall_penalty")*scaling_factor
    egret_model.data["system"]["spinning_reserve_penalty_price"] = penalty_data.get("Spin_shortfall_penalty")*scaling_factor
    egret_model.data["system"]["non_spinning_reserve_penalty_price"] = penalty_data.get("Nonspin_shortfall_penalty")*scaling_factor
    egret_model.data["system"]["supplemental_reserve_penalty_price"] = penalty_data.get("Supplemental_reserve_shortfall_penalty")*scaling_factor
    egret_model.data["system"]["flexible_ramp_penalty_price"] = penalty_data.get("Flexramp_shortfall_penalty")*scaling_factor
    egret_model.data["system"]["contingency_flow_violation_cost"] = penalty_data.get("Contingency_flow_violation_penalty")*scaling_factor
 
def soc_limit_validator(es_soc):
    '''
    Validates the state of charge (SoC) values for energy storage systems.

    Args:
        es_soc: A single value or a list of state of charge values.

    Returns:
        A list of validated state of charge values, ensuring they are within the range [0, 1].
        If a scalar is provided, returns a scalar.
    '''
    is_scalar = isinstance(es_soc, float)
    if is_scalar:
        es_soc = [es_soc]
    validated_soc = []
    for soc_level in es_soc:
        # Check for values slightly above 1.0 (tolerance 1e-5)
        if soc_level - 1 > 0:
            if soc_level - 1 > 1e-5:
                raise ValueError(f"State of Charge {soc_level} exceeds 1.0")
            soc_level = 1
        # Check for values slightly below 0.0 (tolerance 1e-5)
        if soc_level < 0:
            if soc_level < -1e-5:
                raise ValueError(f"State of Charge {soc_level} is below 0.0")
            soc_level = 0
        validated_soc.append(soc_level)
    return validated_soc[0] if is_scalar else validated_soc

def populate_initial_status(source_model, target_model, timestep_minutes):
    '''
    Populates the initial status of generators and storage units in the target model
    based on the final status from the source model.

    Args:
        source_model: The model containing the final status from the previous period.
        target_model: The model to be initialized for the next period.
        timestep_minutes: The length of the timestep in minutes.

    Returns:
        None
    '''
    def update_status_sequence(current_binary, initial_status, timestep_minutes):
        '''
        Updates the status sequence of a generator or storage unit based on the current binary commitment and initial status.

        Args:
            current_binary: The current binary commitment status (1 for ON, 0 for OFF).
            initial_status: The initial status of the generator or storage unit.
            timestep_minutes: The length of the timestep in minutes.

        Returns:
            Updated status (positive for ON, negative for OFF).
        '''
        dt = timestep_minutes / 60
        prev_binary = 1 if initial_status > 0 else 0
        counter = abs(initial_status)
        if current_binary == prev_binary:
            counter = counter + dt
        else:
            counter = dt
        status = counter if current_binary == 1 else -counter
        return status

    # Update generator initial status and output
    for (_, source_gen_dict), (_, target_gen_dict) in zip(
        source_model.elements(element_type='generator', generator_type='thermal'),
        target_model.elements(element_type='generator', generator_type='thermal')
    ):
        current_gen_commitment = source_gen_dict['commitment']["values"][-1]
        previous_gen_status = source_gen_dict['initial_status']
        gen_status = update_status_sequence(current_gen_commitment, previous_gen_status, timestep_minutes)
        target_gen_dict['initial_status'] = gen_status

        current_generation = source_gen_dict['pg']["values"][-1]
        target_gen_dict["initial_p_output"] = current_generation

    # Update storage initial state of charge and (for PHS) mode
    for (source_storage_name, source_storage_dict), (_, target_storage_dict) in zip(
        source_model.elements(element_type='storage'),
        target_model.elements(element_type='storage')
    ):
        current_storage_soc = source_storage_dict['state_of_charge']["values"][-1]
        target_storage_dict['initial_state_of_charge'] = soc_limit_validator(current_storage_soc)
        if source_storage_dict["storage_type"] == "PHS":
            target_storage_dict["initial_gen_mode"] = {}
            target_storage_dict["initial_pump_mode"] = {}
            for unit_num in range(source_storage_dict["num_units"]):
                current_gen_mode = source_storage_dict["Unit_GenMode"][source_storage_name, unit_num]["values"][-1]
                current_pump_mode = source_storage_dict["Unit_PumpMode"][source_storage_name, unit_num]["values"][-1]
                target_storage_dict["initial_gen_mode"][source_storage_name, unit_num] = current_gen_mode
                target_storage_dict["initial_pump_mode"][source_storage_name, unit_num] = current_pump_mode

def evaluate_system_costs_revenue(md_sol, md_DA_sol, evaluate_revenue=False):
    """
    Evaluates the total commitment and production costs for generators and storage units in the market data solution.

    Args:
        md_sol: The market data solution object containing the results of the market simulation.
        md_DA_sol: The DA market data solution (used for reference if needed).

    Returns:
        Tuple: (commitment_costs, production_costs, storage_commitment_costs, storage_production_costs)
    """
    def _time_series_dict(values):
        """Create a time series dictionary."""
        return {'data_type': 'time_series', 'values': values}

    def _get_reserves_revenue(RT_lmp, DA_dict, RT_dict, DA_syst_dict, RT_syst_dict, 
                              DA_area_dict, RT_area_dict, element_type, element_name, 
                              current_hour, resolution, upward_reserves, downward_reserves):
        """Get product values for a specific element and product."""
        for product_name in upward_reserves + downward_reserves:
                DA_value = DA_dict.get(product_name + "_supplied",{}).get("values",[0]*(current_hour+1))[current_hour] 
                DA_syst_price = DA_syst_dict.get(product_name + "_price",{}).get("values",[0]*(current_hour+1))[current_hour]
                DA_area_price = DA_area_dict.get(product_name + "_price",{}).get("values",[0]*(current_hour+1))[current_hour]

                RT_value = RT_dict.get(product_name + "_supplied",{}).get("values",[0])[0]
                RT_syst_price = RT_syst_dict.get(product_name + "_price",{}).get("values",[0])[0]
                RT_area_price = RT_area_dict.get(product_name + "_price",{}).get("values",[0])[0]
                DA_price = DA_syst_price + DA_area_price
                RT_price = RT_syst_price + RT_area_price
                deployment_val =  RT_syst_dict.get(product_name + "_deployed",{}).get("values",[0])[0]

                capacity_revenue = (DA_value * DA_price + (DA_value - RT_value) * RT_price) * resolution / 60
                deployed_energy = deployment_val * RT_value * resolution/60
        
                key = f"{product_name}_supplied"
                if key not in DA_dict and key not in RT_dict:
                    continue
                if product_name in upward_reserves:
                    RT_dict[f"{product_name}_revenue"] = _time_series_dict([capacity_revenue + deployed_energy * RT_lmp])
                else:
                    RT_dict[f"{product_name}_revenue"] = _time_series_dict([capacity_revenue - deployed_energy * RT_lmp])

    commitment_costs = 0
    production_costs = 0
    DA_system_dict = md_DA_sol.data["system"]
    RT_system_dict = md_sol.data["system"]

    for (gen_num, DA_gen_dict),(_, RT_gen_dict) in zip(md_DA_sol.elements(element_type='generator'), md_sol.elements(element_type='generator')):
        commitment_costs += sum(RT_gen_dict.get('commitment_cost', {}).get('values', [0]))
        production_costs += sum(RT_gen_dict['production_cost']["values"])
        rt_resolution = md_sol.data["system"]["time_period_length_minutes"]
        if evaluate_revenue:
            current_hour = datetime.strptime(md_sol.data["system"]["timestamp"][0], "%H:%M").hour
            gen_bus = RT_gen_dict['bus']
            
            current_gen_area = RT_gen_dict['area']
            DA_area_dict = md_DA_sol.data["elements"]["area"][current_gen_area]
            RT_area_dict = md_sol.data["elements"]["area"][current_gen_area]

            DA_lmp = md_DA_sol.data["elements"]["bus"][gen_bus]["lmp"]["values"][current_hour]
            RT_lmp = md_sol.data["elements"]["bus"][gen_bus]["lmp"]["values"][0]

            RT_power = RT_gen_dict["pg"]["values"][0]
            DA_power = DA_gen_dict["pg"]["values"][current_hour]
            
            DA_reserve_price = DA_system_dict.get("reserve_price",{}).get("values",[0]*(current_hour+1))[current_hour]
            DA_reserve_provided = DA_gen_dict.get("reserve_supplied",{}).get("values",[0]*(current_hour+1))[current_hour]
            RT_gen_dict["DA_reserve_revenue"] = _time_series_dict([DA_reserve_price * DA_reserve_provided * rt_resolution / 60])

            energy_revenue = (DA_lmp*DA_power + (RT_power-DA_power)*RT_lmp)*rt_resolution/60
            RT_gen_dict["energy_revenue"] = _time_series_dict([energy_revenue])
            upward_reserves = ["regulation_up", "spinning_reserve", "non_spinning_reserve", "supplemental_reserve", "flexible_ramp_up"]
            downward_reserves = ["regulation_down", "flexible_ramp_down"]

            _get_reserves_revenue(RT_lmp, DA_gen_dict, RT_gen_dict, DA_system_dict, RT_system_dict, DA_area_dict, RT_area_dict, 'generator', 
                                  gen_num, current_hour, rt_resolution, upward_reserves, downward_reserves)
    storage_costs = 0
    for (storage_num, DA_storage_dict),(_, RT_storage_dict) in zip(md_DA_sol.elements(element_type='storage'), md_sol.elements(element_type='storage')):
        storage_costs += sum(RT_storage_dict["operational_cost"]["values"])
        if evaluate_revenue:
            storage_bus = RT_storage_dict['bus']
            current_storage_area = RT_storage_dict['area']
            DA_area_dict = md_DA_sol.data["elements"]["area"][current_storage_area]
            RT_area_dict = md_sol.data["elements"]["area"][current_storage_area]

            DA_lmp = md_DA_sol.data["elements"]["bus"][storage_bus]["lmp"]["values"][current_hour]
            RT_lmp = md_sol.data["elements"]["bus"][storage_bus]["lmp"]["values"][0]

            RT_charge_power = RT_storage_dict["p_charge_only"]["values"][0]
            DA_charge_power = DA_storage_dict["p_charge_only"]["values"][current_hour]
            RT_discharge_power = RT_storage_dict["p_discharge_only"]["values"][0]
            DA_discharge_power = DA_storage_dict["p_discharge_only"]["values"][current_hour]
            RT_relative_power = RT_discharge_power - RT_charge_power
            DA_relative_power = DA_discharge_power - DA_charge_power
            
            energy_revenue = (DA_lmp*DA_relative_power + (RT_relative_power-DA_relative_power)*RT_lmp)*rt_resolution/60
            RT_storage_dict["energy_revenue"] = _time_series_dict([energy_revenue])

            sto_upward_reserves = ["regulation_up", "spinning_reserve", "non_spinning_reserve", "supplemental_reserve"]
            sto_downward_reserves = ["regulation_down"]
            _get_reserves_revenue(RT_lmp, DA_storage_dict, RT_storage_dict, DA_system_dict, RT_system_dict, DA_area_dict, RT_area_dict, 'storage', 
                                  storage_num, current_hour, rt_resolution, sto_upward_reserves, sto_downward_reserves)
            
    return commitment_costs, production_costs + storage_costs

def evaluate_RT_resolution_SoC(pyomo_uc_model, ed_model):
    """
    Evaluates the state of charge (SoC) of storage units at the end of each Real-Time (RT) resolution period.

    Args:
        pyomo_uc_model: The Pyomo model containing the storage variables and params.
        ed_model: The egret ED data model containing the storage elements.

    Returns:
        None. Updates ed_model storage elements in-place with RT_SoC_requirement.
    """
    def _preallocated_list(other_iter):
        """Create a preallocated list."""
        return [None for _ in other_iter]

    def _time_series_dict(values):
        """Create a time series dictionary."""
        return {'data_type': 'time_series', 'values': values}

    m = pyomo_uc_model
    timekey_length = len(ed_model.data["system"]["time_keys"])
    RT_timekeys = list(range(1, timekey_length + 1))
    RT_resolution = ed_model.data["system"]["time_period_length_minutes"]

    for s, storage_dict in ed_model.elements(element_type='storage'):
        initial_soc = storage_dict['initial_state_of_charge']
        SoC_Storage = _preallocated_list(RT_timekeys)

        for current_timekey in RT_timekeys:
            t = (current_timekey * RT_resolution - 1) // 60 + 1  # Corresponding hour of the current time period
            period = current_timekey * RT_resolution / 5
            RT_period_hours = (period % 12) * 5 / 60 if period % 12 != 0 else 1

            # Calculate SoC for each storage type
            if storage_dict["storage_type"] == "Generic":
                if t == 1:
                    SoC_Storage[current_timekey-1] = value(m.StorageSocOnT0[s]) + \
                        (-value(m.PowerDischargeGESS[s, t]) / value(m.OutputEfficiencyEnergy[s]) +
                         value(m.PowerChargeGESS[s, t]) * value(m.InputEfficiencyEnergy[s])) * \
                        RT_period_hours / value(m.MaximumEnergyStorage[s])
                else:
                    SoC_Storage[current_timekey-1] = value(m.SocStorage[s, t-1]) * value(m.ScaledRetentionRate[s]) + \
                        (-value(m.PowerDischargeGESS[s, t]) / value(m.OutputEfficiencyEnergy[s]) +
                         value(m.PowerChargeGESS[s, t]) * value(m.InputEfficiencyEnergy[s])) * \
                        RT_period_hours / value(m.MaximumEnergyStorage[s])

            elif storage_dict["storage_type"] == "BESS":
                if t == 1:
                    SoC_Storage[current_timekey-1] = value(m.StorageSocOnT0[s]) + \
                        (-value(m.PowerDischargeBESS[s, t]) +
                         value(m.PowerChargeBESS[s, t]) * value(m.ConversionEfficiency[s]) +
                         value(m.RegDOWN_efficiency[t]) * value(m.ConversionEfficiency[s]) * value(m.BESS_RegDOWN[s, t]) -
                         value(m.RegUP_efficiency[t]) * value(m.BESS_RegUP[s, t])) * \
                        RT_period_hours / value(m.MaximumEnergyStorage[s])
                else:
                    SoC_Storage[current_timekey-1] = value(m.SocStorage[s, t-1]) * value(m.ScaledRetentionRate[s]) + \
                        (-value(m.PowerDischargeBESS[s, t]) +
                         value(m.PowerChargeBESS[s, t]) * value(m.ConversionEfficiency[s]) +
                         value(m.RegDOWN_efficiency[t]) * value(m.ConversionEfficiency[s]) * value(m.BESS_RegDOWN[s, t]) -
                         value(m.RegUP_efficiency[t]) * value(m.BESS_RegUP[s, t])) * \
                        RT_period_hours / value(m.MaximumEnergyStorage[s])

            elif storage_dict["storage_type"] == "PHS":
                if t == 1:
                    SoC_Storage[current_timekey-1] = value(m.StorageSocOnT0[s]) + \
                        (-value(m.PHS_TotalDischargeFlow[s, t]) / value(m.PHS_GeneratorEfficiency[s]) +
                         value(m.PHS_TotalChargeFlow[s, t]) * value(m.PHS_PumpEfficiency[s]) +
                         value(m.RegDOWN_efficiency[t]) * value(m.PHS_TotalRegDOWN[s, t]) *
                         value(m.PHS_PumpEfficiency[s]) / value(m.PHS_conversion_coefficient[s]) -
                         value(m.RegUP_efficiency[t]) * value(m.PHS_TotalRegUP[s, t]) /
                         (value(m.PHS_GeneratorEfficiency[s]) * value(m.PHS_conversion_coefficient[s]))) * \
                        RT_period_hours / value(m.PHS_UpperReservoirMaxLevel[s])
                else:
                    SoC_Storage[current_timekey-1] = value(m.SocStorage[s, t-1]) + \
                        (-value(m.PHS_TotalDischargeFlow[s, t]) / value(m.PHS_GeneratorEfficiency[s]) +
                         value(m.PHS_TotalChargeFlow[s, t]) * value(m.PHS_PumpEfficiency[s]) +
                         value(m.RegDOWN_efficiency[t]) * value(m.PHS_TotalRegDOWN[s, t]) *
                         value(m.PHS_PumpEfficiency[s]) / value(m.PHS_conversion_coefficient[s]) -
                         value(m.RegUP_efficiency[t]) * value(m.PHS_TotalRegUP[s, t]) /
                         (value(m.PHS_GeneratorEfficiency[s]) * value(m.PHS_conversion_coefficient[s]))) * \
                        RT_period_hours / value(m.PHS_UpperReservoirMaxLevel[s])

        # Validate and assign SoC time series
        SoC_Storage_validated = soc_limit_validator(SoC_Storage)
        storage_dict["RT_SoC_requirement"] = _time_series_dict(SoC_Storage_validated)

def relax_PHS_binaries(model):
    
    for (_, storage_dict) in model.elements(element_type='storage'):
        if storage_dict["storage_type"] == "PHS":
            storage_dict["relax_PHS_vars"] = True
 