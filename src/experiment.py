############################################################################
#               Experiments

# Created by:   Huy Pham
#               University of California, Berkeley

# Date created: August 2023

# Description:  Functions as control for Opensees experiments
############################################################################

# prepare the pandas output of the run
def prepare_results(output_path, design, T_1, Tfb, run_status):
    
    import pandas as pd
    import numpy as np
    from gms import get_gm_ST
    
    # TODO: collect Sa values, collect validation indicator (IDA level)
    num_stories = design['num_stories']
    
    # gather EDPs from opensees output
    # also collecting story 0, which is isol layer
    story_names = ['story_'+str(story)
                   for story in range(0,num_stories+1)]
    story_names.insert(0, 'time')
    
    isol_dof_names = ['time', 'horizontal', 'vertical', 'rotation']
    # forceColumns = ['time', 'iAxial', 'iShearX', 'iShearY',
    #                 'iMomentX','iMomentY', 'iMomentZ',
    #                 'jAxial','jShearX', 'jShearY',
    #                 'jMomentX', 'jMomentY', 'jMomentZ']
    
    # displacements
    inner_col_disp = pd.read_csv(output_path+'inner_col_disp.csv', sep=' ',
                                 header=None, names=story_names)
    outer_col_disp = pd.read_csv(output_path+'outer_col_disp.csv', sep=' ',
                                 header=None, names=story_names)
    
    # velocities (relative)
    inner_col_vel = pd.read_csv(output_path+'inner_col_vel.csv', sep=' ',
                                 header=None, names=story_names)
    outer_col_vel = pd.read_csv(output_path+'outer_col_vel.csv', sep=' ',
                                 header=None, names=story_names)
    
    # accelerations (absolute)
    inner_col_acc = pd.read_csv(output_path+'inner_col_acc.csv', sep=' ',
                                 header=None, names=story_names)
    outer_col_acc = pd.read_csv(output_path+'outer_col_acc.csv', sep=' ',
                                 header=None, names=story_names)
    
    # isolator layer displacement
    isol_disp = pd.read_csv(output_path+'isolator_displacement.csv', sep=' ',
                            header=None, names=isol_dof_names)
    
    # maximum displacement in isol layer
    isol_max_horiz_disp = isol_disp['horizontal'].abs().max()
    
    # drift ratios recorded. diff takes difference with adjacent column
    ft = 12
    h_story = design['h_story']
    inner_col_drift = inner_col_disp.diff(axis=1).drop(columns=['time', 'story_0'])/(h_story*ft)
    outer_col_drift = outer_col_disp.diff(axis=1).drop(columns=['time', 'story_0'])/(h_story*ft)
    
    g = 386.4
    inner_col_acc = inner_col_acc.drop(columns=['time'])/g
    outer_col_acc = outer_col_acc.drop(columns=['time'])/g
    
    inner_col_vel = inner_col_vel.drop(columns=['time'])
    outer_col_vel = outer_col_vel.drop(columns=['time'])
    
    ss_type = design['superstructure_system']
    if ss_type == 'MF':
        ok_thresh = 0.20
    else:
        ok_thresh = 0.075
    # if run was OK, we collect true max values
    if run_status == 0:
        PID = np.maximum(inner_col_drift.abs().max(), 
                         outer_col_drift.abs().max()).tolist()
        PFV = np.maximum(inner_col_vel.abs().max(), 
                         outer_col_vel.abs().max()).tolist()
        PFA = np.maximum(inner_col_acc.abs().max(), 
                         outer_col_acc.abs().max()).tolist()
        RID = np.maximum(inner_col_drift.iloc[-1].abs(), 
                         outer_col_drift.iloc[-1].abs()).tolist()
        
    # if run failed, we find the state corresponding to 0.20 drift across all
    # assumes that once drift crosses 0.20, it only increases (no other floor
    # will exceed 0.20 AND be the highest)
    else:
        drift_df = pd.concat([inner_col_drift, outer_col_drift], axis=1)
        worst_drift = drift_df.abs().max(axis=1)
        drift_sort = worst_drift.iloc[(worst_drift-ok_thresh).abs().argsort()[:1]]
        ok_state = drift_sort.index.values
        
        PID = np.maximum(inner_col_drift.iloc[ok_state.item()].abs(), 
                         outer_col_drift.iloc[ok_state.item()].abs()).tolist()
        
        PFV = np.maximum(inner_col_vel.iloc[ok_state.item()].abs(), 
                         outer_col_vel.iloc[ok_state.item()].abs()).tolist()
        
        PFA = np.maximum(inner_col_acc.iloc[ok_state.item()].abs(), 
                         outer_col_acc.iloc[ok_state.item()].abs()).tolist()
        
        # if collapse, just collect PID as residual
        RID = PID
    
    impact_cols = ['time', 'dirX_left', 'dirX_right']
    impact_force = pd.read_csv(output_path+'impact_forces.csv',
                               sep = ' ', header=None, names=impact_cols)
    impact_thresh = 100   # kips
    if(any(abs(impact_force['dirX_left']) > impact_thresh) or
       any(abs(impact_force['dirX_right']) > impact_thresh)):
        impact_bool = 1
    else:
        impact_bool = 0
        
    Tms_interest = np.array([design['T_m'], 1.0, Tfb])
    Sa_gm = get_gm_ST(design, Tms_interest)
    
    Sa_Tm = Sa_gm[0]
    Sa_1 = Sa_gm[1]
    Sa_Tfb = Sa_gm[2]
        
    # Sa_Tm = get_ST(design, design['T_m'])
    # Sa_1 = get_ST(design, 1.0)
    
    result_dict = {'sa_tm': Sa_Tm,
                   'sa_1': Sa_1,
                   'sa_tfb': Sa_Tfb,
                   'constructed_moat': design['moat_ampli']*design['D_m'],
                   'T_1': T_1,
                   'T_fb': Tfb,
                   'max_isol_disp': isol_max_horiz_disp,
                   'PID': PID,
                   'PFV': PFV,
                   'PFA': PFA,
                   'RID': RID,
                   'impacted': impact_bool,
                   'run_status': run_status
        }
    result_series = pd.Series(result_dict)
    
    final_series = design.append(result_series)
    return(final_series)
    
def collapse_fragility(run):
    system = run.superstructure_system
    peak_drift = max(run.PID)
    
    # collapse as a probability
    from math import log, exp
    from scipy.stats import lognorm
    from scipy.stats import norm
    
    # MF: set 84% collapse at 0.10 drift, 0.25 beta
    if system == 'MF':
        inv_norm = norm.ppf(0.84)
        beta_drift = 0.25
        mean_log_drift = exp(log(0.1) - beta_drift*inv_norm) 
        
    # CBF: set 90% collapse at 0.05 drift, 0.55 beta
    else:
        inv_norm = norm.ppf(0.90)
        beta_drift = 0.55
        mean_log_drift = exp(log(0.05) - beta_drift*inv_norm) 
        
    ln_dist = lognorm(s=beta_drift, scale=mean_log_drift)
    collapse_prob = ln_dist.cdf(peak_drift)
    
    return(peak_drift, collapse_prob)
    
# run the experiment, GM name and scale factor must be baked into design

def run_nlth(design, 
             gm_path='../resource/ground_motions/PEERNGARecords_Unscaled/',
             output_path='./outputs/'):
    
    from building import Building
    
    # generate the building, construct model
    bldg = Building(design)
    bldg.model_frame()
    
    # apply gravity loads, perform eigenvalue analysis, add damping
    bldg.apply_grav_load()
    T_1 = bldg.run_eigen()
    Tfb = bldg.provide_damping(80, method='SP',
                               zeta=[0.05], modes=[1])
    
    # run ground motion
    if bldg.superstructure_system == 'MF':
        dt_default = 0.005
    else:
        dt_default = 0.005
    run_status = bldg.run_ground_motion(design['gm_selected'], 
                                   design['scale_factor'], 
                                   dt_default,
                                   gm_dir=gm_path,
                                   data_dir=output_path)
    
    # lower dt if convergence issues
    if run_status != 0:
        if bldg.superstructure_system == 'MF':
            print('Lowering time step...')
            
            bldg = Building(design)
            bldg.model_frame()
            
            # apply gravity loads, perform eigenvalue analysis, add damping
            bldg.apply_grav_load()
            T_1 = bldg.run_eigen()
            Tfb = bldg.provide_damping(80, method='SP',
                                       zeta=[0.05], modes=[1])
            
            run_status = bldg.run_ground_motion(design['gm_selected'], 
                                                design['scale_factor'], 
                                                0.001,
                                                gm_dir=gm_path,
                                                data_dir=output_path)
        else:
            # print('Cutting time did not work.')
            print('Lowering time step and convergence mode CBF...')
            
            bldg = Building(design)
            bldg.model_frame(convergence_mode=True)
            
            # apply gravity loads, perform eigenvalue analysis, add damping
            bldg.apply_grav_load()
            T_1 = bldg.run_eigen()
            Tfb = bldg.provide_damping(80, method='SP',
                                        zeta=[0.05], modes=[1])
            
            run_status = bldg.run_ground_motion(design['gm_selected'], 
                                                design['scale_factor'], 
                                                0.001,
                                                gm_dir=gm_path,
                                                data_dir=output_path)
        
    # CBF if still no converge, give up
    if run_status != 0:
        if bldg.superstructure_system == 'MF':
            print('Lowering time step one last time...')
            
            bldg = Building(design)
            bldg.model_frame()
            
            # apply gravity loads, perform eigenvalue analysis, add damping
            bldg.apply_grav_load()
            T_1 = bldg.run_eigen()
            Tfb = bldg.provide_damping(80, method='SP',
                                       zeta=[0.05], modes=[1])
            
            run_status = bldg.run_ground_motion(design['gm_selected'], 
                                                design['scale_factor'], 
                                                0.0005,
                                                gm_dir=gm_path,
                                                data_dir=output_path)
        else:
            print('CBF did not converge ...')
            
            # bldg = Building(design)
            # bldg.model_frame(convergence_mode=True)
            
            # # apply gravity loads, perform eigenvalue analysis, add damping
            # bldg.apply_grav_load()
            # T_1 = bldg.run_eigen()
            # Tfb = bldg.provide_damping(80, method='SP',
            #                             zeta=[0.05], modes=[1])
            
            # run_status = bldg.run_ground_motion(design['gm_selected'], 
            #                                     design['scale_factor'], 
            #                                     0.0005,
            #                                     gm_dir=gm_path,
            #                                     data_dir=output_path)
    if run_status != 0:
        print('Recording run and moving on.')
       
    # add a little delay to prevent weird overwriting
    import time
    time.sleep(3)
    
    results_series = prepare_results(output_path, design, T_1, Tfb, run_status)
    return(results_series)
    

def run_doe(prob_target, df_train, df_test, 
            batch_size=10, error_tol=0.15, maxIter=600, conv_tol=1e-2):
    
    import random
    import numpy as np
    import pandas as pd
    
    gm_path='../resource/ground_motions/PEERNGARecords_Unscaled/'
    
    np.random.seed(986)
    random.seed(986)
    from doe import GP
    from db import Database
    
    # TODO: incorporate T_ratio
    
    test_set = GP(df_test)
    covariate_columns = ['moat_ampli', 'RI', 'T_m', 'zeta_e']
    test_set.set_covariates(covariate_columns)
    
    # TODO: temporary change to outcome
    test_set.set_outcome('log_collapse_prob')
    
    sample_bounds = test_set.X.agg(['min', 'max'])
    
    buffer = 4
    doe_reserve_db = Database(maxIter, n_buffer=buffer, seed=131, 
                        struct_sys_list=['MF'], isol_wts=[1, 0])
    
    # drop covariates 
    reserve_df = doe_reserve_db.raw_input
    pregen_designs = reserve_df.drop(columns=[col for col in reserve_df 
                                              if col in covariate_columns])
    
    rmse = 1.0
    batch_idx = 0
    batch_no = 0
    
    rmse_list = []
    mae_list = []
    
    doe_idx = 0
    
    
    import design as ds
    from loads import define_lateral_forces, define_gravity_loads
    from gms import scale_ground_motion
    
    # TODO: check the indices
    while doe_idx < maxIter:
        
        print('========= Run %d of batch %d ==========' % 
              (batch_idx+1, batch_no+1))
        
        if (batch_idx % (batch_size) == 0):
            
            mdl = GP(df_train)
            
            # TODO: temporary change to outcome
            mdl.set_outcome('log_collapse_prob')
            
            mdl.set_covariates(covariate_columns)
            mdl.fit_gpr(kernel_name='rbf_iso')
            
            y_hat = mdl.gpr.predict(test_set.X)
            
            print('===== Training model size:', mdl.X.shape[0], '=====')
            from sklearn.metrics import mean_squared_error, mean_absolute_error
            import numpy as np
            mse = mean_squared_error(test_set.y, y_hat)
            rmse = mse**0.5
            print('Test set RMSE: %.3f' % rmse)

            mae = mean_absolute_error(test_set.y, y_hat)
            print('Test set MAE: %.3f' % mae)
            
            if len(rmse_list) == 0:
                conv = rmse
            else:
                conv = abs(rmse - rmse_list[-1])/rmse_list[-1]
            
            if rmse < error_tol:
                print('Stopping criterion reached. Ending DoE...')
                print('Number of added points: ' + str((batch_idx)*(batch_no)))
                
                rmse_list.append(rmse)
                
                mae_list.append(mae)
                
                return (df_train, rmse_list, mae_list)
            elif conv < conv_tol:
                print('RMSE did not improve beyond convergence tolerance. Ending DoE...')
                print('Number of added points: ' + str((batch_idx)*(batch_no)))
                
                rmse_list.append(rmse)
                
                mae_list.append(mae)
                
                return (df_train, rmse_list, mae_list)
            else:
                pass
            batch_idx = 0
            x_next = mdl.doe_rejection_sampler(batch_size, prob_target, sample_bounds)
            next_df = pd.DataFrame(x_next, columns=covariate_columns)
            print('Convergence not reached yet. Resetting batch index to 0...')
    
        ######################## DESIGN FOR DOE SET ###########################
        #
        # Currently somewhat hardcoded for TFP-MF, 
        #
        # TODO: retry this for one x_next point at a time
    
        # get first set of randomly generated params and merge with a buffer
        # amount of DoE found points (to account for failed designs)
        
        while pregen_designs.shape[0] > 0:
            
            # pop off a pregen design and try to design with it
            batch_df = pregen_designs.head(1)
            pregen_designs.drop(pregen_designs.head(1).index, inplace=True)
            
            next_row = next_df.iloc[[batch_idx]].set_index(batch_df.index)
        
            batch_df = pd.concat([batch_df, next_row], axis=1)
        
            # # ensure that batch_df has columns needed for design (T_m)
            # # approximate fixed based fundamental period
            # Ct = get_Ct(struct_type)
            # x_Tfb = get_x_Tfb(struct_type)
            # h_n = np.sum(hsx)/12.0
            # T_fb = Ct*(h_n**x_Tfb)
            
            # design
            batch_df[['W', 
                   'W_s', 
                   'w_fl', 
                   'P_lc',
                   'all_w_cases',
                   'all_Plc_cases']] = batch_df.apply(lambda row: define_gravity_loads(row),
                                                    axis='columns', result_type='expand')
                                                  
            all_tfp_designs = batch_df.apply(lambda row: ds.design_TFP(row),
                                           axis='columns', result_type='expand')
            
            all_tfp_designs.columns = ['mu_1', 'mu_2', 'R_1', 'R_2', 
                                       'T_e', 'k_e', 'zeta_e', 'D_m']
            
            tfp_designs = all_tfp_designs.loc[(all_tfp_designs['R_1'] >= 10.0) &
                                              (all_tfp_designs['R_1'] <= 50.0) &
                                              (all_tfp_designs['R_2'] <= 190.0) &
                                              (all_tfp_designs['zeta_e'] <= 0.27)]
            
            # retry if design didn't work
            if tfp_designs.shape[0] == 0:
                continue
            
            tfp_designs = tfp_designs.drop(columns=['zeta_e'])
            batch_df = pd.concat([batch_df, tfp_designs], axis=1)
            
            # get lateral force and design structures
            batch_df[['wx', 
                   'hx', 
                   'h_col', 
                   'hsx', 
                   'Fx', 
                   'Vs',
                   'T_fbe']] = batch_df.apply(lambda row: define_lateral_forces(row),
                                        axis='columns', result_type='expand')
                                              
            all_mf_designs = batch_df.apply(lambda row: ds.design_MF(row),
                                             axis='columns', 
                                             result_type='expand')
              
            all_mf_designs.columns = ['beam', 'column', 'flag']
            
            # keep the designs that look sensible
            mf_designs = all_mf_designs.loc[all_mf_designs['flag'] == False]
            mf_designs = mf_designs.dropna(subset=['beam','column'])
             
            mf_designs = mf_designs.drop(['flag'], axis=1)
            
            if mf_designs.shape[0] == 0:
                continue
          
            # get the design params of those bearings
            batch_df = pd.concat([batch_df, mf_designs], axis=1)
            
            
            batch_df[['gm_selected',
                     'scale_factor',
                     'sa_avg']] = batch_df.apply(lambda row: scale_ground_motion(row),
                                                axis='columns', result_type='expand')
               
            break
        
        
        bldg_result = run_nlth(batch_df.iloc[0], gm_path)
        result_df = pd.DataFrame(bldg_result).T
        
        
        result_df[['max_drift',
           'collapse_prob']] = result_df.apply(lambda row: collapse_fragility(row),
                                                axis='columns', result_type='expand')
                               
        from numpy import log
        result_df['log_collapse_prob'] = log(result_df['collapse_prob'])
        result_df['T_ratio'] = result_df['T_m'] / result_df['T_fb']
        
        # if run is successful and is batch marker, record error metric
        if (batch_idx % (batch_size) == 0):
            rmse_list.append(rmse)
            mae_list.append(mae)
        
        batch_idx += 1
        doe_idx += 1

        # attach to existing data
        df_train = pd.concat([df_train, result_df], axis=0)
        
    print('DoE did not converge within maximum iteration specified.')
    return df_train, rmse_list, mae_list
    