############################################################################
#               chapter 4 figures

# Created by:   Huy Pham
#               University of California, Berkeley

############################################################################
import sys
# caution: path[0] is reserved for script path (or '' in REPL)
sys.path.insert(1, '../')

import pickle
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from doe import GP

plt.close('all')

main_obj = pd.read_pickle("../../data/tfp_mf_db.pickle")

# with open("../../data/tfp_mf_db.pickle", 'rb') as picklefile:
#     main_obj = pickle.load(picklefile)
    
main_obj.calculate_collapse()

df_raw = main_obj.ops_analysis

# remove the singular outlier point
from scipy import stats
df = df_raw[np.abs(stats.zscore(df_raw['collapse_prob'])) < 10].copy()

# df = df_whole.head(100).copy()

df['max_drift'] = df.PID.apply(max)
df['log_drift'] = np.log(df['max_drift'])

df['max_velo'] = df.PFV.apply(max)
df['max_accel'] = df.PFA.apply(max)

df['T_ratio'] = df['T_m'] / df['T_fb']
df['T_ratio_e'] = df['T_m'] / df['T_fbe']
pi = 3.14159
g = 386.4

zetaRef = [0.02, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50]
BmRef   = [0.8, 1.0, 1.2, 1.5, 1.7, 1.9, 2.0]
df['Bm'] = np.interp(df['zeta_e'], zetaRef, BmRef)

df['gap_ratio'] = (df['constructed_moat']*4*pi**2)/ \
    (g*(df['sa_tm']/df['Bm'])*df['T_m']**2)
    


#%%
# make a generalized 2D plotting grid, defaulted to gap and Ry
# grid is based on the bounds of input data
def make_2D_plotting_space(X, res, x_var='gap_ratio', y_var='RI', 
                           all_vars=['gap_ratio', 'RI', 'T_ratio', 'zeta_e'],
                           third_var_set = None, fourth_var_set = None,
                           x_bounds=None, y_bounds=None):
    
    if x_bounds == None:
        x_min = min(X[x_var])
        x_max = max(X[x_var])
    else:
        x_min = x_bounds[0]
        x_max = x_bounds[1]
    if y_bounds == None:
        y_min = min(X[y_var])
        y_max = max(X[y_var])
    else:
        y_min = y_bounds[0]
        y_max = y_bounds[1]
    xx, yy = np.meshgrid(np.linspace(x_min,
                                     x_max,
                                     res),
                         np.linspace(y_min,
                                     y_max,
                                     res))

    rem_vars = [i for i in all_vars if i not in [x_var, y_var]]
    third_var = rem_vars[0]
    fourth_var = rem_vars[-1]
       
    xx = xx
    yy = yy
    
    if third_var_set is None:
        third_var_val= X[third_var].median()
    else:
        third_var_val = third_var_set
    if fourth_var_set is None:
        fourth_var_val = X[fourth_var].median()
    else:
        fourth_var_val = fourth_var_set
    
    
    X_pl = pd.DataFrame({x_var:xx.ravel(),
                         y_var:yy.ravel(),
                         third_var:np.repeat(third_var_val,
                                             res*res),
                         fourth_var:np.repeat(fourth_var_val, 
                                              res*res)})
    X_plot = X_pl[all_vars]
                         
    return(X_plot)

# hard-coded
def make_design_space(res, fix_zeta=None):
    if fix_zeta is None:
        xx, yy, uu, vv = np.meshgrid(np.linspace(0.6, 1.5,
                                                 res),
                                     np.linspace(0.5, 2.25,
                                                 res),
                                     np.linspace(2.0, 5.0,
                                                 res),
                                     np.linspace(0.1, 0.25,
                                                 res))
    else:
        xx, yy, uu, vv = np.meshgrid(np.linspace(0.6, 1.5,
                                                 res),
                                     np.linspace(0.5, 2.25,
                                                 res),
                                     2.0,
                                     fix_zeta)
            
                                 
    X_space = pd.DataFrame({'gap_ratio':xx.ravel(),
                         'RI':yy.ravel(),
                         'T_ratio':uu.ravel(),
                         'zeta_e':vv.ravel()})

    return(X_space)

#%% collapse fragility def

label_size=18
plt.rcParams["text.usetex"] = True
plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"

mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 

# collapse as a probability
from scipy.stats import lognorm
from math import log, exp

collapse_drift_def_mu_std = 0.1


from scipy.stats import norm
inv_norm = norm.ppf(0.84)
beta_drift = 0.25
mean_log_drift = exp(log(collapse_drift_def_mu_std) - beta_drift*inv_norm) # 0.9945 is inverse normCDF of 0.84
# mean_log_drift = 0.05
ln_dist = lognorm(s=beta_drift, scale=mean_log_drift)

label_size = 16
clabel_size = 12
x = np.linspace(0, 0.15, 200)

mu = log(mean_log_drift)

ln_dist = lognorm(s=beta_drift, scale=mean_log_drift)
p = ln_dist.cdf(np.array(x))


fig, ax = plt.subplots(1, 1, figsize=(8,6))

ax.plot(x, p, label='Collapse (peak)', color='blue')

mu_irr = log(0.01)
ln_dist_irr = lognorm(s=0.3, scale=exp(mu_irr))
p_irr = ln_dist_irr.cdf(np.array(x))

# ax.plot(x, p_irr, color='red', label='Irreparable (residual)')

axis_font = 20
subt_font = 18
xright = 0.0
xleft = 0.15
ax.set_ylim([0,1])
ax.set_xlim([0, xleft])
ax.set_ylabel('Collapse probability', fontsize=axis_font)
ax.set_xlabel('Peak drift ratio', fontsize=axis_font)

ax.vlines(x=exp(mu), ymin=0, ymax=0.5, color='blue', linestyle=":")
ax.hlines(y=0.5, xmin=xright, xmax=exp(mu), color='blue', linestyle=":")
ax.text(0.01, 0.52, r'$\theta = %.3f$'% mean_log_drift , fontsize=axis_font, color='blue')
ax.plot([exp(mu)], [0.5], marker='*', markersize=15, color="blue", linestyle=":")

upper = ln_dist.ppf(0.84)
ax.vlines(x=upper, ymin=0, ymax=0.84, color='blue', linestyle=":")
ax.hlines(y=0.84, xmin=xright, xmax=upper, color='blue', linestyle=":")
ax.text(0.01, 0.87, r'$\theta = %.3f$' % upper, fontsize=axis_font, color='blue')
ax.plot([upper], [0.84], marker='*', markersize=15, color="blue", linestyle=":")

lower= ln_dist.ppf(0.16)
ax.vlines(x=lower, ymin=0, ymax=0.16, color='blue', linestyle=":")
ax.hlines(y=0.16, xmin=xright, xmax=lower, color='blue', linestyle=":")
ax.text(0.01, 0.19, r'$\theta = %.3f$' % lower, fontsize=axis_font, color='blue')
ax.plot([lower], [0.16], marker='*', markersize=15, color="blue", linestyle=":")


# ax.set_title('Replacement fragility definition', fontsize=axis_font)
ax.grid()
# ax.legend(fontsize=label_size, loc='upper center')
# plt.show()
# plt.savefig('./figures/collapse_def.eps')

#%% base-set data
'''
kernel_name = 'rbf_ard'

mdl = GP(df)
covariate_list = ['gap_ratio', 'RI', 'T_ratio', 'zeta_e']
mdl.set_covariates(covariate_list)
mdl.set_outcome('collapse_prob')
mdl.fit_gpr(kernel_name=kernel_name)


res = 75

X_plot = make_2D_plotting_space(mdl.X, res, x_var='T_ratio', y_var='zeta_e', 
                           all_vars=['gap_ratio', 'RI', 'T_ratio', 'zeta_e'],
                           third_var_set = 1.0, fourth_var_set=2.0)

import time
t0 = time.time()

fmu_base, fs1_base = mdl.gpr.predict(X_plot, return_std=True)
fs2_base = fs1_base**2

tp = time.time() - t0
print("GPR collapse prediction for %d inputs in %.3f s" % (X_plot.shape[0],
                                                               tp))

#%% base-set, Tm_zeta plot
plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
axis_font = 20
subt_font = 18
import matplotlib as mpl
label_size = 16
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 

x_var = 'T_ratio'
xx = X_plot[x_var]
y_var = 'zeta_e'
yy = X_plot[y_var]

x_pl = np.unique(xx)
y_pl = np.unique(yy)

# collapse predictions
xx_pl, yy_pl = np.meshgrid(x_pl, y_pl)
Z = fmu_base.reshape(xx_pl.shape)

plt.figure(figsize=(8,6))
# plt.imshow(
#     Z,
#     interpolation="nearest",
#     extent=(xx_pl.min(), xx_pl.max(),
#             yy_pl.min(), yy_pl.max()),
#     aspect="auto",
#     origin="lower",
#     cmap=plt.cm.Blues,
# ) 
lvls = [0.025, 0.05, 0.10, 0.2, 0.3]
cs = plt.contour(xx_pl, yy_pl, Z, linewidths=1.1, cmap='Blues', vmin=-1)
plt.clabel(cs, fontsize=clabel_size)
plt.scatter(df['T_ratio'], df['zeta_e'], 
            c=df['collapse_prob'],
            edgecolors='k', s=20.0, cmap=plt.cm.Blues, vmax=5e-1)
# plt.xlim([0.5,2.0])
# plt.ylim([0.5, 2.25])
plt.xlabel('T ratio', fontsize=axis_font)
plt.ylabel(r'$\zeta_M$', fontsize=axis_font)
plt.grid(True)
plt.title('Collapse risk using full 400 points', fontsize=axis_font)
plt.show()

#%%
X_plot = make_2D_plotting_space(mdl.X, res, 
                                third_var_set=3.0, fourth_var_set=0.2)

import time
t0 = time.time()

fmu_base, fs1_base = mdl.gpr.predict(X_plot, return_std=True)
fs2_base = fs1_base**2

tp = time.time() - t0
print("GPR collapse prediction for %d inputs in %.3f s" % (X_plot.shape[0],
                                                               tp))

#%% base-set, gap_Ry plot

plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
axis_font = 20
subt_font = 18
import matplotlib as mpl
label_size = 16
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 

x_var = 'gap_ratio'
xx = X_plot[x_var]
y_var = 'RI'
yy = X_plot[y_var]

x_pl = np.unique(xx)
y_pl = np.unique(yy)

# collapse predictions
xx_pl, yy_pl = np.meshgrid(x_pl, y_pl)
Z = fmu_base.reshape(xx_pl.shape)

plt.figure(figsize=(8,6))
# plt.imshow(
#     Z,
#     interpolation="nearest",
#     extent=(xx_pl.min(), xx_pl.max(),
#             yy_pl.min(), yy_pl.max()),
#     aspect="auto",
#     origin="lower",
#     cmap=plt.cm.Blues,
# ) 
lvls = [0.025, 0.05, 0.10, 0.2, 0.3]
cs = plt.contour(xx_pl, yy_pl, Z, linewidths=1.1, cmap='Blues', vmin=-1)
plt.clabel(cs, fontsize=clabel_size)
plt.scatter(df['gap_ratio'], df['RI'], 
            c=df['collapse_prob'],
            edgecolors='k', s=20.0, cmap=plt.cm.Blues, vmax=5e-1)
plt.xlim([0.5,2.0])
plt.ylim([0.5, 2.25])
plt.xlabel('Gap ratio', fontsize=axis_font)
plt.ylabel(r'$R_y$', fontsize=axis_font)
plt.grid(True)
plt.title('Collapse risk using full 400 points', fontsize=axis_font)
plt.show()

#%% base-set, gap_Ry plot, kernel ridge

mdl.fit_kernel_ridge()
fmu_base = mdl.kr.predict(X_plot).ravel()


#%% 10% design

X_design_cand = make_design_space(25)

X_baseline = pd.DataFrame(np.array([[1.0, 2.0, 3.0, 0.15]]),
                          columns=['gap_ratio', 'RI', 'T_ratio', 'zeta_e'])
baseline_risk, baseline_fs1 = mdl.gpr.predict(X_baseline, return_std=True)
baseline_risk = baseline_risk.item()
baseline_fs2 = baseline_fs1**2
baseline_fs1 = baseline_fs1.item()
baseline_fs2 = baseline_fs2.item()

t0 = time.time()
fmu_design, fs1_design = mdl.gpr.predict(X_design_cand, return_std=True)
fs2_design = fs1_design**2

tp = time.time() - t0
print("GPR collapse prediction for %d inputs in %.3f s" % (X_design_cand.shape[0],
                                                                tp))


'''
#%% Calculate upfront cost of data

# TODO: normalize cost for building size

def get_steel_coefs(df, steel_per_unit=1.25):
    n_bays = df.num_bays
    n_stories = df.num_stories
    # ft
    L_bldg = df.L_bldg
    L_beam = df.L_bay
    h_story = df.h_story
    
    # weights
    W = df.W
    Ws = df.W_s
    
    
    all_beams = df.beam
    all_cols = df.column
    
    # sum of per-length-weight of all floors
    col_wt = [[float(member.split('X',1)[1]) for member in col_list] 
                       for col_list in all_cols]
    beam_wt = [[float(member.split('X',1)[1]) for member in beam_list] 
                       for beam_list in all_beams]
    col_all_wt = np.array(list(map(sum, col_wt)))
    beam_all_wt = np.array(list(map(sum, beam_wt)))
    
    # find true steel costs
    n_frames = 4
    n_cols = 4*n_bays
    
    total_floor_col_length = np.array(n_cols*h_story, dtype=float)
    total_floor_beam_length = np.array(L_beam * n_bays * n_frames, dtype=float)
        
    total_col_wt = col_all_wt*total_floor_col_length 
    total_beam_wt = beam_all_wt*total_floor_beam_length
    
    bldg_wt = total_col_wt + total_beam_wt
    
    steel_cost = steel_per_unit*bldg_wt
    bldg_sf = np.array(n_stories * L_bldg**2, dtype=float)
    steel_cost_per_sf = steel_cost/bldg_sf
    
    # find design base shear as a feature
    pi = 3.14159
    g = 386.4
    kM = (1/g)*(2*pi/df['T_m'])**2
    S1 = 1.017
    Dm = g*S1*df['T_m']/(4*pi**2*df['Bm'])
    Vb = Dm * kM * Ws / 2
    Vst = Vb*(Ws/W)**(1 - 2.5*df['zeta_e'])
    Vs = np.array(Vst/df['RI']).reshape(-1,1)
    
    # linear regress cost as f(base shear)
    from sklearn.linear_model import LinearRegression
    reg = LinearRegression()
    reg.fit(X=Vs, y=steel_cost_per_sf)
    return({'coef':reg.coef_, 'intercept':reg.intercept_})

def calc_upfront_cost(X_test, steel_coefs,
                      land_cost_per_sqft=2837/(3.28**2),
                      W=3037.5, Ws=2227.5):
    
    from scipy.interpolate import interp1d
    zeta_ref = [0.02, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50]
    Bm_ref = [0.8, 1.0, 1.2, 1.5, 1.7, 1.9, 2.0]
    interp_f = interp1d(zeta_ref, Bm_ref)
    Bm = interp_f(X_test['zeta_e'])
    
    # estimate Tm
    
    from loads import estimate_period
    
    # current dummy structure: 4 bays, 4 stories
    # 13 ft stories, 30 ft bays
    X_query = X_test.copy()
    X_query['superstructure_system'] = 'MF'
    X_query['h_bldg'] = 4*13.0
    X_query['T_fbe'] = X_query.apply(lambda row: estimate_period(row),
                                                     axis='columns', result_type='expand')
    
    X_query['T_m'] = X_query['T_fbe'] * X_query['T_ratio']
    
    # calculate moat gap
    pi = 3.14159
    g = 386.4
    S1 = 1.017
    SaTm = S1/X_query['T_m']
    moat_gap = X_query['gap_ratio'] * (g*(SaTm/Bm)*X_query['T_m']**2)/(4*pi**2)
    
    # calculate design base shear
    kM = (1/g)*(2*pi/X_query['T_m'])**2
    Dm = g*S1*X_query['T_m']/(4*pi**2*Bm)
    Vb = Dm * kM * Ws / 2
    Vst = Vb*(Ws/W)**(1 - 2.5*X_query['zeta_e'])
    Vs = Vst/X_query['RI']
    
    # steel coefs now represent cost/sf as a function of Vs
    steel_cost_per_sf = steel_coefs['intercept'] + steel_coefs['coef']*Vs
    # land_area = 2*(90.0*12.0)*moat_gap - moat_gap**2
    
    bldg_area = 4 * (30*4)**2
    steel_cost = steel_cost_per_sf * bldg_area
    land_area = (4*30*12.0 + moat_gap)**2
    land_cost = land_cost_per_sqft/144.0 * land_area
    
    return({'total': steel_cost + land_cost,
            'steel': steel_cost,
            'land': land_cost})
   
''' 
#%% baseline & prediction from 400-base-set


risk_thresh = 0.1
space_collapse_pred = pd.DataFrame(fmu_design, columns=['collapse probability'])
ok_risk = X_design_cand.loc[space_collapse_pred['collapse probability']<=
                      risk_thresh]

# get_structural_cmp_MF(df, metadata)
steel_price = 2.00
coef_dict = get_steel_coefs(df, steel_per_unit=steel_price)

baseline_costs = calc_upfront_cost(X_baseline, coef_dict)
baseline_total = baseline_costs['total'].item()
baseline_steel = baseline_costs['steel'].item()
baseline_land = baseline_costs['land'].item()

# least upfront cost of the viable designs

print('========== Baseline design ============')
print('Design target', f'{risk_thresh:.2%}')
print('Upfront cost of selected design: ',
      f'${baseline_total:,.2f}')
print('Predicted collapse risk: ',
      f'{baseline_risk:.2%}')
print(X_baseline)

import warnings
warnings.filterwarnings('ignore')

upfront_costs = calc_upfront_cost(ok_risk, coef_dict, W=W_seis, Ws=W_super)
cheapest_design_idx = upfront_costs['total'].idxmin()
design_upfront_cost = upfront_costs['total'].min()
design_steel_cost = upfront_costs['steel'][cheapest_design_idx]
design_land_cost = upfront_costs['land'][cheapest_design_idx]
# least upfront cost of the viable designs
best_design = ok_risk.loc[cheapest_design_idx]
design_collapse_risk = space_collapse_pred.iloc[cheapest_design_idx]['collapse probability']
warnings.resetwarnings()

print('========== Inverse design ============')
print('Design target', f'{risk_thresh:.2%}')
print('Upfront cost of selected design: ',
      f'${design_upfront_cost:,.2f}')
print('Steel cost of selected design, ',
      f'${design_steel_cost:,.2f}')
print('Land cost of selected design, ',
      f'${design_land_cost:,.2f}')
print('Predicted collapse risk: ',
      f'{design_collapse_risk:.2%}')
print(best_design)

# some issues that may lead to poor design
# data is lacking in T_ratio and zeta realm
# be careful if the considered design space falls outside of the 
# available data space (model reverts to 0)

'''
#%%
def simple_cull_df(input_df, dominates, *args):
    pareto_df = pd.DataFrame(columns=input_df.columns)
    candidateRowNr = 0
    dominated_df = pd.DataFrame(columns=input_df.columns)
    while True:
        candidateRow = input_df.iloc[[candidateRowNr]]
        input_df = input_df.drop(index=candidateRow.index)
        rowNr = 0
        nonDominated = True
        while input_df.shape[0] != 0 and rowNr < input_df.shape[0]:
            row = input_df.iloc[[rowNr]]
            if dominates(candidateRow, row, *args):
                # If it is worse on all features remove the row from the array
                input_df = input_df.drop(index=row.index)
                dominated_df = dominated_df.append(row)
            elif dominates(row, candidateRow, *args):
                nonDominated = False
                dominated_df = dominated_df.append(candidateRow)
                rowNr += 1
            else:
                rowNr += 1

        if nonDominated:
            # add the non-dominated point to the Pareto frontier
            pareto_df = pareto_df.append(candidateRow)

        if input_df.shape[0] == 0:
            break
    return pareto_df, dominated_df

def dominates_pd(row, candidate_row, mdl, cost, coefs):
    row_pr = mdl.predict(row).item()
    cand_pr = mdl.predict(candidate_row).item()
    
    row_cost = cost(row, coefs).item()
    cand_cost = cost(candidate_row, coefs).item()
    
    return ((row_pr < cand_pr) and (row_cost < cand_cost))

# Faster than is_pareto_efficient_simple, but less readable.
def is_pareto_efficient(costs, return_mask = True):
    """
    Find the pareto-efficient points
    :param costs: An (n_points, n_costs) array
    :param return_mask: True to return a mask
    :return: An array of indices of pareto-efficient points.
        If return_mask is True, this will be an (n_points, ) boolean array
        Otherwise it will be a (n_efficient_points, ) integer array of indices.
    """
    is_efficient = np.arange(costs.shape[0])
    n_points = costs.shape[0]
    next_point_index = 0  # Next index in the is_efficient array to search for
    while next_point_index<len(costs):
        nondominated_point_mask = np.any(costs<costs[next_point_index], axis=1)
        nondominated_point_mask[next_point_index] = True
        is_efficient = is_efficient[nondominated_point_mask]  # Remove dominated points
        costs = costs[nondominated_point_mask]
        next_point_index = np.sum(nondominated_point_mask[:next_point_index])+1
    if return_mask:
        is_efficient_mask = np.zeros(n_points, dtype = bool)
        is_efficient_mask[is_efficient] = True
        return is_efficient_mask
    else:
        return is_efficient
    
'''
all_costs = calc_upfront_cost(X_design_cand, coef_dict)
constr_costs = all_costs['total']
predicted_risk = space_collapse_pred['collapse probability']
pareto_array = np.array([constr_costs, predicted_risk]).transpose()

t0 = time.time()
pareto_mask = is_pareto_efficient(pareto_array)
tp = time.time() - t0

print("Culled %d points in %.3f s" % (X_design_cand.shape[0], tp))

X_pareto = X_design_cand.iloc[pareto_mask]
risk_pareto = predicted_risk.iloc[pareto_mask]
cost_pareto = constr_costs.iloc[pareto_mask]

plt.figure(figsize=(8,6))
# plt.imshow(
#     Z,
#     interpolation="nearest",
#     extent=(xx_pl.min(), xx_pl.max(),
#             yy_pl.min(), yy_pl.max()),
#     aspect="auto",
#     origin="lower",
#     cmap=plt.cm.Blues,
# ) 
plt.scatter(risk_pareto, cost_pareto, 
            edgecolors='k', s=20.0)
plt.xlabel('Collapse risk', fontsize=axis_font)
plt.ylabel('Construction cost', fontsize=axis_font)
plt.grid(True)
plt.title('Pareto front', fontsize=axis_font)
plt.show()


plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
axis_font = 20
subt_font = 18
import matplotlib as mpl
label_size = 16
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 

x_var = 'gap_ratio'
xx = X_plot[x_var]
y_var = 'RI'
yy = X_plot[y_var]

x_pl = np.unique(xx)
y_pl = np.unique(yy)

# collapse predictions
xx_pl, yy_pl = np.meshgrid(x_pl, y_pl)

fig = plt.figure(figsize=(14,6))
ax1=fig.add_subplot(1, 2, 1)
ax1.scatter(X_pareto['gap_ratio'], X_pareto['RI'], 
            c=risk_pareto,
            edgecolors='k', s=20.0, cmap=plt.cm.Blues, vmax=5e-1)
ax1.set_xlim([0.5,2.0])
ax1.set_ylim([0.45, 2.3])
ax1.set_xlabel('Gap ratio', fontsize=axis_font)
ax1.set_ylabel(r'$R_y$', fontsize=axis_font)
ax1.grid(True)
ax1.set_title('Pareto efficient designs', fontsize=axis_font)

ax2=fig.add_subplot(1, 2, 2)
ax2.scatter(X_pareto['T_ratio'], X_pareto['zeta_e'], 
            c=risk_pareto,
            edgecolors='k', s=20.0, cmap=plt.cm.Blues, vmax=5e-1)
ax2.set_xlabel('T ratio', fontsize=axis_font)
ax2.set_ylabel(r'$\zeta_M$', fontsize=axis_font)
ax2.grid(True)
ax2.set_title('Pareto efficient designs', fontsize=axis_font)
fig.tight_layout()
'''

###############################################################################
# DOE
###############################################################################

#%% doe data set GP
import time

plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
axis_font = 20
subt_font = 20
import matplotlib as mpl
label_size = 18
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 
clabel_size = 16

main_obj_doe = pd.read_pickle('../../data/tfp_mf_db_doe_prestrat.pickle')
df_doe = main_obj_doe.doe_analysis


# from ast import literal_eval
# df_doe = pd.read_csv('../../data/doe/temp_save.csv', 
#                      converters={'PID': literal_eval,
#                                  'PFV': literal_eval,
#                                  'PFA': literal_eval,
#                                  'RID': literal_eval,
#                                  'beam': literal_eval,
#                                  'column': literal_eval})


kernel_name = 'rbf_iso'

collapse_drift_def_mu_std = 0.1
#%%
from experiment import collapse_fragility
df_doe[['max_drift',
   'collapse_prob']] = df_doe.apply(
       lambda row: collapse_fragility(row, mf_drift_mu_plus_std=collapse_drift_def_mu_std), 
       axis='columns', result_type='expand')



# df_doe = df_doe.drop(columns=['index'])

df_doe['max_drift'] = df_doe.PID.apply(max)
df_doe['log_drift'] = np.log(df_doe['max_drift'])

df_doe['max_velo'] = df_doe.PFV.apply(max)
df_doe['max_accel'] = df_doe.PFA.apply(max)

df_doe['T_ratio'] = df_doe['T_m'] / df_doe['T_fb']
df_doe['T_ratio_e'] = df_doe['T_m'] / df_doe['T_fbe']
pi = 3.14159
g = 386.4

zetaRef = [0.02, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50]
BmRef   = [0.8, 1.0, 1.2, 1.5, 1.7, 1.9, 2.0]
df_doe['Bm'] = np.interp(df_doe['zeta_e'], zetaRef, BmRef)

df_doe['gap_ratio'] = (df_doe['constructed_moat']*4*pi**2)/ \
    (g*(df_doe['sa_tm']/df_doe['Bm'])*df_doe['T_m']**2)

    
print('% impact of DoE set:', sum(df_doe['impacted'])/df_doe.shape[0])
print('average drift:', df_doe['max_drift'].mean())

df_init = df_doe.head(50)

from loads import define_gravity_loads
config_dict = {
    'S_1' : 1.017,
    'k_ratio' : 10,
    'Q': 0.06,
    'num_frames' : 2,
    'num_bays' : 4,
    'num_stories' : 4,
    'L_bay': 30.0,
    'h_story': 13.0,
    'isolator_system' : 'TFP',
    'superstructure_system' : 'MF',
    'S_s' : 2.2815
}
(W_seis, W_super, w_on_frame, P_on_leaning_column,
       all_w_cases, all_plc_cases) = define_gravity_loads(config_dict)

#%%


mdl_doe = GP(df_doe)
covariate_list = ['gap_ratio', 'RI', 'T_ratio', 'zeta_e']
mdl_doe.set_covariates(covariate_list)
mdl_doe.set_outcome('collapse_prob')

mdl_doe.fit_gpr(kernel_name=kernel_name)

X_baseline = pd.DataFrame(np.array([[1.0, 2.0, 3.0, 0.15]]),
                          columns=['gap_ratio', 'RI', 'T_ratio', 'zeta_e'])


baseline_risk, baseline_fs1 = mdl_doe.gpr.predict(X_baseline, return_std=True)
baseline_risk = baseline_risk.item()
baseline_fs2 = baseline_fs1**2
baseline_fs1 = baseline_fs1.item()
baseline_fs2 = baseline_fs2.item()

steel_price = 2.0
coef_dict = get_steel_coefs(df_doe, steel_per_unit=steel_price)
baseline_costs = calc_upfront_cost(X_baseline, coef_dict, W=W_seis, Ws=W_super)

baseline_total = baseline_costs['total'].item()
baseline_steel = baseline_costs['steel'].item()
baseline_land = baseline_costs['land'].item()

risk_thresh = 0.1

print('========== Baseline design (DoE) ============')
print('Design target', f'{risk_thresh:.2%}')
print('Upfront cost of selected design: ',
      f'${baseline_total:,.2f}')
print('Predicted collapse risk: ',
      f'{baseline_risk:.2%}')
print(X_baseline)
T_fbe = 0.925
Bm = np.interp(X_baseline['zeta_e'], zetaRef, BmRef)
dm = g*1.017*X_baseline['T_ratio']*0.925/(4*pi**2*Bm)*X_baseline['gap_ratio']
dm_val = dm.iloc[0]
print('Displacement capacity (cm):',
      dm_val*2.54)

design_res = 20
X_design_cand = make_design_space(design_res, fix_zeta=0.15)


t0 = time.time()
fmu_design, fs1_design = mdl_doe.gpr.predict(X_design_cand, return_std=True)
fs2_design = fs1_design**2

tp = time.time() - t0
print("GPR collapse prediction for %d inputs in %.3f s" % (X_design_cand.shape[0],
                                                                tp))


risk_thresh = 0.1
space_collapse_pred = pd.DataFrame(fmu_design, columns=['collapse probability'])
ok_risk = X_design_cand.loc[space_collapse_pred['collapse probability']<=
                      risk_thresh]

import warnings
warnings.filterwarnings('ignore')

upfront_costs = calc_upfront_cost(ok_risk, coef_dict, W=W_seis, Ws=W_super)
cheapest_design_idx = upfront_costs['total'].idxmin()
design_upfront_cost = upfront_costs['total'].min()
design_steel_cost = upfront_costs['steel'][cheapest_design_idx]
design_land_cost = upfront_costs['land'][cheapest_design_idx]
# least upfront cost of the viable designs
best_design = ok_risk.loc[cheapest_design_idx]
design_collapse_risk = space_collapse_pred.iloc[cheapest_design_idx]['collapse probability']
warnings.resetwarnings()

print('========== Inverse design ============')
print('Design target', f'{risk_thresh:.2%}')
print('Upfront cost of selected design: ',
      f'${design_upfront_cost:,.2f}')
print('Steel cost of selected design, ',
      f'${design_steel_cost:,.2f}')
print('Land cost of selected design, ',
      f'${design_land_cost:,.2f}')
print('Predicted collapse risk: ',
      f'{design_collapse_risk:.2%}')
print(best_design)
T_fbe = 0.925
Bm = np.interp(best_design['zeta_e'], zetaRef, BmRef)
dm = g*1.017*best_design['T_ratio']*0.925/(4*pi**2*Bm)*best_design['gap_ratio']
print('Displacement capacity (cm):',
      dm*2.54)

risk_thresh = 0.05
space_collapse_pred = pd.DataFrame(fmu_design, columns=['collapse probability'])
ok_risk = X_design_cand.loc[space_collapse_pred['collapse probability']<=
                      risk_thresh]

import warnings
warnings.filterwarnings('ignore')

upfront_costs = calc_upfront_cost(ok_risk, coef_dict, W=W_seis, Ws=W_super)
cheapest_design_idx = upfront_costs['total'].idxmin()
design_upfront_cost = upfront_costs['total'].min()
design_steel_cost = upfront_costs['steel'][cheapest_design_idx]
design_land_cost = upfront_costs['land'][cheapest_design_idx]
# least upfront cost of the viable designs
best_design = ok_risk.loc[cheapest_design_idx]
design_collapse_risk = space_collapse_pred.iloc[cheapest_design_idx]['collapse probability']
warnings.resetwarnings()

print('========== Inverse design ============')
print('Design target', f'{risk_thresh:.2%}')
print('Upfront cost of selected design: ',
      f'${design_upfront_cost:,.2f}')
print('Steel cost of selected design, ',
      f'${design_steel_cost:,.2f}')
print('Land cost of selected design, ',
      f'${design_land_cost:,.2f}')
print('Predicted collapse risk: ',
      f'{design_collapse_risk:.2%}')
print(best_design)
T_fbe = 0.925
Bm = np.interp(best_design['zeta_e'], zetaRef, BmRef)
dm = g*1.017*best_design['T_ratio']*0.925/(4*pi**2*Bm)*best_design['gap_ratio']
print('Displacement capacity (cm):',
      dm*2.54)

risk_thresh = 0.025
space_collapse_pred = pd.DataFrame(fmu_design, columns=['collapse probability'])
ok_risk = X_design_cand.loc[space_collapse_pred['collapse probability']<=
                      risk_thresh]

import warnings
warnings.filterwarnings('ignore')

upfront_costs = calc_upfront_cost(ok_risk, coef_dict, W=W_seis, Ws=W_super)
cheapest_design_idx = upfront_costs['total'].idxmin()
design_upfront_cost = upfront_costs['total'].min()
design_steel_cost = upfront_costs['steel'][cheapest_design_idx]
design_land_cost = upfront_costs['land'][cheapest_design_idx]
# least upfront cost of the viable designs
best_design = ok_risk.loc[cheapest_design_idx]
design_collapse_risk = space_collapse_pred.iloc[cheapest_design_idx]['collapse probability']
warnings.resetwarnings()

print('========== Inverse design ============')
print('Design target', f'{risk_thresh:.2%}')
print('Upfront cost of selected design: ',
      f'${design_upfront_cost:,.2f}')
print('Steel cost of selected design, ',
      f'${design_steel_cost:,.2f}')
print('Land cost of selected design, ',
      f'${design_land_cost:,.2f}')
print('Predicted collapse risk: ',
      f'{design_collapse_risk:.2%}')
print(best_design)
T_fbe = 0.925
Bm = np.interp(best_design['zeta_e'], zetaRef, BmRef)
dm = g*1.017*best_design['T_ratio']*0.925/(4*pi**2*Bm)*best_design['gap_ratio']
print('Displacement capacity (cm):',
      dm*2.54)


#%% Prediction 3ds

# as an example, let's do gap vs Ry as T evolves
plt.close('all')

plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
title_font=20
axis_font = 18
subt_font = 18
label_size = 16
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 

res = 75
plt_density = 200
x_var = 'gap_ratio'
y_var = 'RI'
X_plot = make_2D_plotting_space(mdl_doe.X, res, x_var=x_var, y_var=y_var, 
                            all_vars=['gap_ratio', 'RI', 'T_ratio', 'zeta_e'],
                            third_var_set = 2.0, fourth_var_set = 0.15)
xx = X_plot[x_var]
yy = X_plot[y_var]
x_pl = np.unique(xx)
y_pl = np.unique(yy)
xx_pl, yy_pl = np.meshgrid(x_pl, y_pl)

fmu_3d, fs1_3d = mdl_doe.gpr.predict(X_plot, return_std=True)
fs2_3d = fs1_3d**2

Z_3d = fmu_3d.reshape(xx_pl.shape)

fig = plt.figure(figsize=(11, 9))
ax=fig.add_subplot(2, 2, 1, projection='3d')

# Plot the surface.
surf = ax.plot_surface(xx_pl, yy_pl, Z_3d, cmap=plt.cm.Spectral_r,
                        linewidth=0, antialiased=False,
                        alpha=0.7, vmin=0, vmax=0.075)

# df = df_doe.copy()
df = df_doe[(df_doe['T_ratio'] < 2.5)]
ax.scatter(df[x_var][:plt_density], df[y_var][:plt_density], 
            df['collapse_prob'][:plt_density],
            edgecolors='k')

ax.set_xlabel(r'$GR$', fontsize=axis_font, linespacing=0.5)
ax.set_ylabel(r'$R_y$', fontsize=axis_font, linespacing=1.0)
ax.set_zlabel(r'Collapse probability', fontsize=axis_font, linespacing=3.0)
ax.set_title(r'a) $T_M/T_{fb}=2.0$', fontsize=title_font)
# ax.set_xlim([2, 5])
ax.set_zlim([0, 1])
# plt.show()

# #################################

X_plot = make_2D_plotting_space(mdl_doe.X, res, x_var=x_var, y_var=y_var, 
                            all_vars=['gap_ratio', 'RI', 'T_ratio', 'zeta_e'],
                            third_var_set = 3.0, fourth_var_set = 0.15)
xx = X_plot[x_var]
yy = X_plot[y_var]
x_pl = np.unique(xx)
y_pl = np.unique(yy)
xx_pl, yy_pl = np.meshgrid(x_pl, y_pl)

fmu_3d, fs1_3d = mdl_doe.gpr.predict(X_plot, return_std=True)
fs2_3d = fs1_3d**2

Z_3d = fmu_3d.reshape(xx_pl.shape)

ax=fig.add_subplot(2, 2, 2, projection='3d')

# Plot the surface.
surf = ax.plot_surface(xx_pl, yy_pl, Z_3d, cmap=plt.cm.Spectral_r,
                        linewidth=0, antialiased=False,
                        alpha=0.7, vmin=0, vmax=0.075)

df = df_doe[(df_doe['T_ratio'] < 3.5) & (df_doe['T_ratio'] > 2.5)]
ax.scatter(df[x_var][:plt_density], df[y_var][:plt_density], 
            df['collapse_prob'][:plt_density],
            edgecolors='k')

ax.set_xlabel(r'$GR$', fontsize=axis_font, linespacing=0.5)
ax.set_ylabel(r'$R_y$', fontsize=axis_font, linespacing=1.0)
ax.set_zlabel(r'Collapse probability', fontsize=axis_font, linespacing=3.0)
ax.set_title(r'b) $T_M/T_{fb}=3.0$', fontsize=title_font)
# ax.set_xlim([2, 5])
ax.set_zlim([0, 1])

# #################################

X_plot = make_2D_plotting_space(mdl_doe.X, res, x_var=x_var, y_var=y_var, 
                            all_vars=['gap_ratio', 'RI', 'T_ratio', 'zeta_e'],
                            third_var_set = 4.0, fourth_var_set = 0.15)
xx = X_plot[x_var]
yy = X_plot[y_var]
x_pl = np.unique(xx)
y_pl = np.unique(yy)
xx_pl, yy_pl = np.meshgrid(x_pl, y_pl)

fmu_3d, fs1_3d = mdl_doe.gpr.predict(X_plot, return_std=True)
fs2_3d = fs1_3d**2

Z_3d = fmu_3d.reshape(xx_pl.shape)

ax=fig.add_subplot(2, 2, 3, projection='3d')

# Plot the surface.
surf = ax.plot_surface(xx_pl, yy_pl, Z_3d, cmap=plt.cm.Spectral_r,
                        linewidth=0, antialiased=False,
                        alpha=0.7, vmin=0, vmax=0.075)

df = df_doe[(df_doe['T_ratio'] < 4.5) & (df_doe['T_ratio'] > 3.5)]
ax.scatter(df[x_var][:plt_density], df[y_var][:plt_density], 
            df['collapse_prob'][:plt_density],
            edgecolors='k')

ax.set_xlabel(r'$GR$', fontsize=axis_font, linespacing=0.5)
ax.set_ylabel(r'$R_y$', fontsize=axis_font, linespacing=1.0)
ax.set_zlabel(r'Collapse probability', fontsize=axis_font, linespacing=3.0)
ax.set_title(r'c) $T_M/T_{fb}=4.0$', fontsize=title_font)
# ax.set_xlim([2, 5])
ax.set_zlim([0, 1])

# #################################

X_plot = make_2D_plotting_space(mdl_doe.X, res, x_var=x_var, y_var=y_var, 
                            all_vars=['gap_ratio', 'RI', 'T_ratio', 'zeta_e'],
                            third_var_set = 5.0, fourth_var_set = 0.15)
xx = X_plot[x_var]
yy = X_plot[y_var]
x_pl = np.unique(xx)
y_pl = np.unique(yy)
xx_pl, yy_pl = np.meshgrid(x_pl, y_pl)

fmu_3d, fs1_3d = mdl_doe.gpr.predict(X_plot, return_std=True)
fs2_3d = fs1_3d**2

Z_3d = fmu_3d.reshape(xx_pl.shape)

ax=fig.add_subplot(2, 2, 4, projection='3d')

# Plot the surface.
surf = ax.plot_surface(xx_pl, yy_pl, Z_3d, cmap=plt.cm.Spectral_r,
                        linewidth=0, antialiased=False,
                        alpha=0.7, vmin=0, vmax=0.075)

df = df_doe[(df_doe['T_ratio'] > 3.5) ]
ax.scatter(df[x_var][:plt_density], df[y_var][:plt_density], 
            df['collapse_prob'][:plt_density],
            edgecolors='k')

ax.set_xlabel(r'$GR$', fontsize=axis_font, linespacing=0.5)
ax.set_ylabel(r'$R_y$', fontsize=axis_font, linespacing=1.0)
ax.set_zlabel(r'Collapse probability', fontsize=axis_font, linespacing=3.0)
ax.set_title(r'd) $T_M/T_{fb}=5.0$', fontsize=title_font)
# ax.set_xlim([2, 5])
ax.set_zlim([0, 1])

fig.tight_layout(w_pad=0.0)
# plt.savefig('./figures/surf.pdf')
# plt.show()

#%%

df = df_doe.copy()
plt.figure(figsize=(8,6))
# plt.imshow(
#     Z,
#     interpolation="nearest",
#     extent=(xx_pl.min(), xx_pl.max(),
#             yy_pl.min(), yy_pl.max()),
#     aspect="auto",
#     origin="lower",
#     cmap=plt.cm.Blues,
# ) 
plt.scatter(df['gap_ratio'], df['T_ratio'])
# plt.xlim([0.5,2.0])
# plt.ylim([0.5, 2.25])
plt.xlabel('$GR$', fontsize=axis_font)
plt.ylabel(r'$T_M/T_{fb}$', fontsize=axis_font)
plt.grid(True)
# plt.title('Collapse risk using full 400 points', fontsize=axis_font)
plt.show()

