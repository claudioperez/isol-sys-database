import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pred import Prediction, predict_DV
plt.close('all')
idx = pd.IndexSlice
pd.options.display.max_rows = 30

import warnings
warnings.filterwarnings('ignore')

## temporary spyder debugger error hack
import collections
collections.Callable = collections.abc.Callable

from scipy.stats import lognorm
from math import log, exp
from scipy.stats import norm
inv_norm = norm.ppf(0.84)
beta_drift = 0.25
mean_log_drift = exp(log(0.1) - beta_drift*inv_norm) # 0.9945 is inverse normCDF of 0.84
ln_dist = lognorm(s=beta_drift, scale=mean_log_drift)


#%% Calculate upfront cost of data
# TODO: use PACT to get the replacement cost of these components
# TODO: include the deckings/slabs for more realistic initial costs

def get_steel_coefs(df, steel_per_unit=1.25, W=3037.5, Ws=2227.5):
    col_str = df['col']
    beam_str = df['beam']
    rbeam_str = df['roofBeam']
    
    col_wt = np.array([float(member.split('X',1)[1]) for member in col_str])
    beam_wt = np.array([float(member.split('X',1)[1]) for member in beam_str])
    rbeam_wt = np.array([float(member.split('X',1)[1]) for member in rbeam_str])
    
    # find true steel costs
    n_frames = 4
    n_cols = 12
    L_col = 39.0 #ft
    
    n_beam_per_frame = 6
    L_beam = 30.0 #ft
    
    n_roof_per_frame = 3
    L_roof = 30.0 #ft
    
    bldg_wt = ((L_col * n_cols)*col_wt +
               (L_beam * n_beam_per_frame * n_frames)*beam_wt +
               (L_roof * n_roof_per_frame * n_frames)*rbeam_wt
               )
    
    steel_cost = steel_per_unit*bldg_wt
    
    # find design base shear as a feature
    pi = 3.14159
    g = 386.4
    kM = (1/g)*(2*pi/df['Tm'])**2
    S1 = 1.017
    Dm = g*S1*df['Tm']/(4*pi**2*df['Bm'])
    Vb = Dm * kM * Ws / 2
    Vst = Vb*(Ws/W)**(1 - 2.5*df['zetaM'])
    Vs = np.array(Vst/df['RI']).reshape(-1,1)
    
    # linear regress cost as f(base shear)
    from sklearn.linear_model import LinearRegression
    reg = LinearRegression()
    reg.fit(X=Vs, y=steel_cost)
    return({'coef':reg.coef_, 'intercept':reg.intercept_})
    
# TODO: add economy of scale for land
    
# TODO: investigate upfront cost's influence by Tm
    
def calc_upfront_cost(X_query, steel_coefs,
                      land_cost_per_sqft=2837/(3.28**2),
                      W=3037.5, Ws=2227.5):
    
    from scipy.interpolate import interp1d
    zeta_ref = [0.02, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50]
    Bm_ref = [0.8, 1.0, 1.2, 1.5, 1.7, 1.9, 2.0]
    interp_f = interp1d(zeta_ref, Bm_ref)
    Bm = interp_f(X_query['zetaM'])
    
    # calculate moat gap
    pi = 3.14159
    g = 386.4
    S1 = 1.017
    SaTm = S1/X_query['Tm']
    moat_gap = X_query['gapRatio'] * (g*(SaTm/Bm)*X_query['Tm']**2)/(4*pi**2)
    
    # calculate design base shear
    kM = (1/g)*(2*pi/X_query['Tm'])**2
    Dm = g*S1*X_query['Tm']/(4*pi**2*Bm)
    Vb = Dm * kM * Ws / 2
    Vst = Vb*(Ws/W)**(1 - 2.5*X_query['zetaM'])
    Vs = np.array(Vst/X_query['RI']).reshape(-1,1)
    
    steel_cost = np.array(steel_coefs['intercept'] +
                          steel_coefs['coef']*Vs).ravel()
    # land_area = 2*(90.0*12.0)*moat_gap - moat_gap**2
    land_area = (90.0*12.0 + moat_gap)**2
    land_cost = land_cost_per_sqft/144.0 * land_area
    
    return(steel_cost + land_cost)

#%%

database_path = './data/tfp_mf/'
database_file = 'run_data.csv'

results_path = './results/tfp_mf/'
results_file = 'loss_estimate_data.csv'

val_dir = './data/tfp_mf_val/'
val_dir_loss = './results/tfp_mf_val/validation/'
val_file = 'addl_TFP_val.csv'

baseline_dir = './data/tfp_mf_val/'
baseline_dir_loss = './results/tfp_mf_val/baseline/'
baseline_file = 'addl_TFP_baseline.csv'

val_loss = pd.read_csv(val_dir_loss+'loss_estimate_data.csv', index_col=None)
base_loss = pd.read_csv(baseline_dir_loss+'loss_estimate_data.csv', index_col=None)

val_run = pd.read_csv(val_dir+val_file, index_col=None)
base_run = pd.read_csv(baseline_dir+baseline_file, index_col=None)

loss_data = pd.read_csv(results_path+results_file, 
                        index_col=None)
full_isolation_data = pd.read_csv(database_path+database_file, 
                                  index_col=None)
cost_var = 'cost_50%'
time_var = 'time_u_50%'

df = pd.concat([full_isolation_data, loss_data], axis=1)
df['max_drift'] = df[["driftMax1", "driftMax2", "driftMax3"]].max(axis=1)
df['collapse_probs'] = ln_dist.cdf(np.array(df['max_drift']))
df['repair_time'] = df[time_var]/50.0

df_val = pd.concat([val_run, val_loss], axis=1)
df_val['max_drift'] = df_val[["driftMax1", "driftMax2", "driftMax3"]].max(axis=1)
df_val['collapse_probs'] = ln_dist.cdf(np.array(df_val['max_drift']))
df_val['repair_time'] = df[time_var]/50.0

df_base = pd.concat([base_run, base_loss], axis=1)
df_base['max_drift'] = df_base[["driftMax1", "driftMax2", "driftMax3"]].max(axis=1)
df_base['collapse_probs'] = ln_dist.cdf(np.array(df_base['max_drift']))
df_val['repair_time'] = df[time_var]/50.0



#%% engineering data
plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
axis_font = 20
subt_font = 18
import matplotlib as mpl
label_size = 16
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 

bins = pd.IntervalIndex.from_tuples([(0.2, 0.5), (0.5, 1.0), (1.0, 1.5), (1.5, 3.5)])
labels=['tiny', 'small', 'okay', 'large']
df['gap_bin'] = pd.cut(df['gapRatio'], bins=bins, labels=labels)
df_count = df.groupby('gap_bin')['max_drift'].apply(lambda x: (x>=0.10).sum()).reset_index(name='count')
a = df.groupby(['gap_bin']).size()
df_count['percent'] = df_count['count']/a

plt.close('all')
fig, ax1 = plt.subplots(1, 1, figsize=(9,6))
import seaborn as sns
sns.stripplot(data=df, x="max_drift", y="gap_bin", orient="h",
              hue='RI', size=10,
              ax=ax1, legend='brief', palette='bone')
sns.boxplot(y="gap_bin", x= "max_drift", data=df,  showfliers=False,
            boxprops={'facecolor': 'none'}, meanprops={'color': 'black'},
            width=0.6, ax=ax1)

plt.setp(ax1.get_legend().get_texts(), fontsize=subt_font) # for legend text
plt.setp(ax1.get_legend().get_title(), fontsize=axis_font)
ax1.get_legend().get_title().set_text(r'$R_y$') # for legend title

ax1.set_ylabel('Gap ratio range', fontsize=axis_font)
ax1.set_xlabel('Peak interstory drift (PID)', fontsize=axis_font)
plt.xlim([0.0, 0.20])
fig.tight_layout()

#%% collapse fragility def
import numpy as np
from scipy.stats import norm
inv_norm = norm.ppf(0.84)
x = np.linspace(0, 0.15, 200)
mu = log(0.1)- 0.25*inv_norm
sigma = 0.25;

ln_dist = lognorm(s=sigma, scale=exp(mu))
p = ln_dist.cdf(np.array(x))

plt.close('all')
fig, ax = plt.subplots(1, 1, figsize=(8,6))

ax.plot(x, p)

axis_font = 20
subt_font = 18
ax.set_ylim([0,1])
ax.set_xlim([0, 0.15])
ax.set_ylabel('Collapse probability', fontsize=axis_font)
ax.set_xlabel('Peak interstory drift (PID)', fontsize=axis_font)

ax.vlines(x=exp(mu), ymin=0, ymax=0.5, color='red')
ax.hlines(y=0.5, xmin=0.0, xmax=exp(mu), color='red')
ax.text(0.001, 0.51, r'50% collapse: PID = 0.078', fontsize=axis_font, color='red')
ax.plot([exp(mu)], [0.5], marker='*', markersize=15, color="red")

ax.vlines(x=0.1, ymin=0, ymax=0.84, color='red')
ax.hlines(y=0.84, xmin=0.0, xmax=0.1, color='red')
ax.text(0.001, 0.85, r'84% collapse: PID = 0.10', fontsize=axis_font, color='red')
ax.plot([0.10], [0.84], marker='*', markersize=15, color="red")

lower= ln_dist.ppf(0.16)
ax.vlines(x=lower, ymin=0, ymax=0.16, color='red')
ax.hlines(y=0.16, xmin=0.0, xmax=lower, color='red')
ax.text(0.001, 0.17, r'16% collapse: PID = 0.061', fontsize=axis_font, color='red')
ax.plot([lower], [0.16], marker='*', markersize=15, color="red")

ax.set_title('Collapse fragility definition', fontsize=axis_font)
ax.grid()
#%% overall data distribution
plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
axis_font = 20
subt_font = 14
title_font=22
import matplotlib as mpl
label_size = 16
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 

plt.close('all')

fig, ax1 = plt.subplots(1, 1, figsize=(8, 6))

sns.scatterplot(data=df, x="gapRatio", y="RI",
              hue='Tm', size='zetaM',
              legend='brief', palette='Blues',
              ax=ax1)

legend_handle = ax1.legend(fontsize=subt_font, loc='center right',
                          title_fontsize=subt_font)
legend_handle.get_texts()[0].set_text(r'$T_M$')
legend_handle.get_texts()[6].set_text(r'$\zeta_M$')
ax1.set_xlabel(r'Gap ratio', fontsize=axis_font)
ax1.set_ylabel(r'$R_y$', fontsize=axis_font)
ax1.set_title(r'Input distribution', fontsize=title_font)
ax1.set_xlim([0.3, 2.5])
ax1.grid()

# plt.close('all')
# import seaborn as sns
# with sns.plotting_context(rc={"legend.fontsize":axis_font}):
#     rel = sns.relplot(data=df, x="gapRatio", y="RI",
#                   hue='Tm', size='zetaM',
#                   legend='brief', palette='Blues')

# # plt.setp(ax1.get_legend().get_texts(), fontsize=subt_font) # for legend text
# # plt.setp(ax1.get_legend().get_title(), fontsize=axis_font) # for legend title


# for ax in rel.axes.flat:
#      ax.set_xlabel("Gap ratio", visible=True, fontsize=axis_font)
#      ax.set_ylabel(r'$R_y$', visible=True, fontsize=axis_font)
     
#      legend_handle = ax.legend(fontsize=subt_font, loc='center right',
#                                 title_fontsize=subt_font)
# (rel.tight_layout(w_pad=0))

#%% loss data

plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
axis_font = 20
subt_font = 14
title_font=22
import matplotlib as mpl
label_size = 16
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 

plt.close('all')
# make grid and plot classification predictions

fig = plt.figure(figsize=(13, 10))
ax1 = fig.add_subplot(2, 2, 1)

sc = sns.scatterplot(data=df,
                     x='gapRatio', y='RI',
                     hue='cost_50%', size='Tm',
                     ax=ax1)

# legend_handles, _= ax1.get_legend_handles_labels()
# ax1.legend(fontsize=subt_font)

ax1.set_title('Median repair cost', fontsize=title_font)
ax1.set_ylabel(r'$R_y$', fontsize=axis_font)
ax1.set_xlabel(None)
ax1.grid()

legend_handle = ax1.legend(fontsize=subt_font, loc='center right',
                           title_fontsize=subt_font)

legend_handle.get_texts()[0].set_text('Cost ($M)')
legend_handle.get_texts()[6].set_text(r'$T_M$')

ax2 = fig.add_subplot(2, 2, 2)

sc = sns.scatterplot(data=df,
                     x='gapRatio', y='RI',
                     hue='repair_time', size='Tm',
                     ax=ax2, legend='brief')

ax2.set_title('Median downtime', fontsize=title_font)
ax2.set_xlabel(None)
ax2.set_ylabel(None)
ax2.grid()

legend_handle = ax2.legend(fontsize=subt_font, loc='center right',
                           title_fontsize=subt_font)

legend_handle.get_texts()[0].set_text('Days')
legend_handle.get_texts()[5].set_text(r'$T_M$')

ax3 = fig.add_subplot(2, 2, 3)

sc = sns.scatterplot(data=df,
                     x='gapRatio', y='RI',
                     hue='max_drift', size='Tm',
                     ax=ax3, legend='brief')

ax3.set_title('Peak story drift', fontsize=title_font)
ax3.set_xlabel(r'Gap ratio (GR)', fontsize=axis_font)
ax3.set_ylabel(r'$R_y$', fontsize=axis_font)
ax3.grid()

legend_handle = ax3.legend(fontsize=subt_font, loc='center right',
                           title_fontsize=subt_font)

legend_handle.get_texts()[0].set_text('PID')
legend_handle.get_texts()[6].set_text(r'$T_M$')

ax4 = fig.add_subplot(2, 2, 4)

sc = sns.scatterplot(data=df,
                     x='gapRatio', y='RI',
                     hue='collapse_freq', size='Tm',
                     ax=ax4, legend='brief')

ax4.set_title('Collapse frequency', fontsize=title_font)
ax4.set_xlabel(r'Gap ratio (GR)', fontsize=axis_font)
ax4.set_ylabel(None)
ax4.grid()

legend_handle = ax4.legend(fontsize=subt_font, loc='center right',
                           title_fontsize=subt_font)

legend_handle.get_texts()[0].set_text('% collapse')
legend_handle.get_texts()[7].set_text(r'$T_M$')

fig.tight_layout()

#%% impact effect

plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
axis_font = 18
subt_font = 18
label_size = 16
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 

#plt.close('all')
import seaborn as sns

# make grid and plot classification predictions

fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(13, 4))
sns.boxplot(y=cost_var, x= "impacted", data=df,  showfliers=False,
            boxprops={'facecolor': 'none'},
            width=0.6, ax=ax1)
sns.stripplot(x='impacted', y=cost_var, data=df, ax=ax1, jitter=True)
ax1.set_title('Median repair cost', fontsize=subt_font)
ax1.set_ylabel('Cost [USD]', fontsize=axis_font)
ax1.set_xlabel('Impact', fontsize=axis_font)
ax1.set_yscale('log')

sns.boxplot(y=time_var, x= "impacted", data=df,  showfliers=False,
            boxprops={'facecolor': 'none'},
            width=0.6, ax=ax2)
sns.stripplot(x='impacted', y=time_var, data=df, ax=ax2, jitter=True)
ax2.set_title('Median sequential repair time', fontsize=subt_font)
ax2.set_ylabel('Time [worker-day]', fontsize=axis_font)
ax2.set_xlabel('Impact', fontsize=axis_font)
ax2.set_yscale('log')

sns.boxplot(y="replacement_freq", x= "impacted", data=df,  showfliers=False,
            boxprops={'facecolor': 'none'},
            width=0.5, ax=ax3)
sns.stripplot(x='impacted', y='replacement_freq', data=df, ax=ax3, jitter=True)
ax3.set_title('Replacement frequency', fontsize=subt_font)
ax3.set_ylabel('Replacement frequency', fontsize=axis_font)
ax3.set_xlabel('Impact', fontsize=axis_font)
fig.tight_layout()

#%% ml training

# make prediction objects for impacted and non-impacted datasets
df_hit = df[df['impacted'] == 1]
mdl_hit = Prediction(df_hit)
mdl_hit.set_outcome(cost_var)
mdl_hit.test_train_split(0.2)

df_miss = df[df['impacted'] == 0]
mdl_miss = Prediction(df_miss)
mdl_miss.set_outcome(cost_var)
mdl_miss.test_train_split(0.2)

hit = Prediction(df_hit)
hit.set_outcome('impacted')
hit.test_train_split(0.2)

miss = Prediction(df_miss)
miss.set_outcome('impacted')
miss.test_train_split(0.2)

df_miss = df[df['impacted'] == 0]
mdl_miss = Prediction(df_miss)
mdl_miss.set_outcome(cost_var)
mdl_miss.test_train_split(0.2)

mdl_time_hit = Prediction(df_hit)
mdl_time_hit.set_outcome(time_var)
mdl_time_hit.test_train_split(0.2)

mdl_time_miss = Prediction(df_miss)
mdl_time_miss.set_outcome(time_var)
mdl_time_miss.test_train_split(0.2)

mdl_drift_hit = Prediction(df_hit)
mdl_drift_hit.set_outcome('max_drift')
mdl_drift_hit.test_train_split(0.2)

mdl_drift_miss = Prediction(df_miss)
mdl_drift_miss.set_outcome('max_drift')
mdl_drift_miss.test_train_split(0.2)

#%% fit impact (gp classification)

# prepare the problem
mdl = Prediction(df)
mdl.set_outcome('impacted')
mdl.test_train_split(0.2)

mdl.fit_gpc(kernel_name='rbf_iso')

# predict the entire dataset
preds_imp = mdl.gpc.predict(mdl.X)
probs_imp = mdl.gpc.predict_proba(mdl.X)

# we've done manual CV to pick the hyperparams that trades some accuracy
# in order to lower false negatives
from sklearn.metrics import confusion_matrix

tn, fp, fn, tp = confusion_matrix(mdl.y, preds_imp).ravel()
print('False negatives: ', fn)
print('False positives: ', fp)

#%% Classification plot

plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
axis_font = 20
subt_font = 18
import matplotlib as mpl
label_size = 16
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 

plt.close('all')
# make grid and plot classification predictions

fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(14, 4.5))
plt.setp((ax1, ax2, ax3), xticks=np.arange(0.5, 4.0, step=0.5))

xvar = 'gapRatio'
yvar = 'RI'
X_plot = mdl.make_2D_plotting_space(100, x_var=xvar, y_var=yvar)
xx = mdl.xx
yy = mdl.yy
Z = mdl.gpc.predict_proba(mdl.X_plot)[:, 1]
Z = Z.reshape(xx.shape)

#ax1.imshow(
#        Z,
#        interpolation="nearest",
#        extent=(xx.min(), xx.max(),
#                yy.min(), yy.max()),
#        aspect="auto",
#        origin="lower",
#        cmap=plt.cm.Greys,
#    )

plt_density = 50
cs = ax1.contour(xx, yy, Z, linewidths=1.1, cmap='Blues', vmin=-1,
                 levels=np.linspace(0.1,1.0,num=10))
ax1.clabel(cs, fontsize=label_size)

# sc = ax3.scatter(mdl.X_train[xvar][:plt_density],
#             mdl.X_train[yvar][:plt_density],
#             s=30, c=mdl.y_train[:plt_density],
#             cmap=plt.cm.copper, edgecolors='w')

#ax1.contour(xx, yy, Z, levels=[0.5], linewidths=2,
#            linestyles="dashed", colors='black')

ax1.scatter(hit.X_train[xvar][:plt_density],
            hit.X_train[yvar][:plt_density],
            s=30, c='darkblue', marker='v', edgecolors='k', label='Impacted')

ax1.scatter(miss.X_train[xvar][:plt_density],
            miss.X_train[yvar][:plt_density],
            s=30, c='azure', edgecolors='k', label='No impact')

ax1.set_xlim(0.3, 2.5)
ax1.set_title(r'$T_M = 3.25$ s, $\zeta_M = 0.15$', fontsize=subt_font)
ax1.set_xlabel(r'Gap ratio (GR)', fontsize=axis_font)
ax1.set_ylabel(r'$R_y$', fontsize=axis_font)

####################################################################
xvar = 'gapRatio'
yvar = 'Tm'
X_plot = mdl.make_2D_plotting_space(100, x_var=xvar, y_var=yvar)
xx = mdl.xx
yy = mdl.yy
Z = mdl.gpc.predict_proba(mdl.X_plot)[:, 1]
Z = Z.reshape(xx.shape)

#ax1.imshow(
#        Z,
#        interpolation="nearest",
#        extent=(xx.min(), xx.max(),
#                yy.min(), yy.max()),
#        aspect="auto",
#        origin="lower",
#        cmap=plt.cm.Greys,
#    )

plt_density = 50
cs = ax2.contour(xx, yy, Z, linewidths=1.1, cmap='Blues', vmin=-1,
                 levels=np.linspace(0.1,1.0,num=10))
ax2.clabel(cs, fontsize=label_size)

#ax1.contour(xx, yy, Z, levels=[0.5], linewidths=2,
#            linestyles="dashed", colors='black')

ax2.scatter(hit.X_train[xvar][:plt_density],
            hit.X_train[yvar][:plt_density],
            s=30, c='darkblue', marker='v', edgecolors='k', label='Impacted')

ax2.scatter(miss.X_train[xvar][:plt_density],
            miss.X_train[yvar][:plt_density],
            s=30, c='azure', edgecolors='k', label='No impact')

ax2.set_xlim(0.3, 2.5)
ax2.set_title(r'$R_y= 1.25$ , $\zeta_M = 0.15$', fontsize=subt_font)
ax2.set_xlabel(r'Gap ratio', fontsize=axis_font)
ax2.set_ylabel(r'$T_M$', fontsize=axis_font)

####################################################################
xvar = 'gapRatio'
yvar = 'zetaM'
X_plot = mdl.make_2D_plotting_space(100, x_var=xvar, y_var=yvar)
xx = mdl.xx
yy = mdl.yy
Z = mdl.gpc.predict_proba(mdl.X_plot)[:, 1]
Z = Z.reshape(xx.shape)

#ax1.imshow(
#        Z,
#        interpolation="nearest",
#        extent=(xx.min(), xx.max(),
#                yy.min(), yy.max()),
#        aspect="auto",
#        origin="lower",
#        cmap=plt.cm.Greys,
#    )

plt_density = 50
cs = ax3.contour(xx, yy, Z, linewidths=1.1, cmap='Blues', vmin=-1,
                 levels=np.linspace(0.1,1.0,num=10))
ax3.clabel(cs, fontsize=label_size)

#ax1.contour(xx, yy, Z, levels=[0.5], linewidths=2,
#            linestyles="dashed", colors='black')

ax3.scatter(hit.X_train[xvar][:plt_density],
            hit.X_train[yvar][:plt_density],
            s=30, c='darkblue', marker='v', edgecolors='k', label='Impacted')

ax3.scatter(miss.X_train[xvar][:plt_density],
            miss.X_train[yvar][:plt_density],
            s=30, c='azure', edgecolors='k', label='No impact')

# sc = ax3.scatter(mdl.X_train[xvar][:plt_density],
#             mdl.X_train[yvar][:plt_density],
#             s=30, c=mdl.y_train[:plt_density],
#             cmap=plt.cm.copper, edgecolors='w')

ax3.set_xlim(0.3, 2.5)
ax3.set_title(r'$R_y= 1.25$ , $T_M = 3.25$ s', fontsize=subt_font)
ax3.set_xlabel(r'Gap ratio', fontsize=axis_font)
ax3.set_ylabel(r'$\zeta_M$', fontsize=axis_font)

ax3.legend(loc="lower right", fontsize=subt_font)

# lg = ax3.legend(*sc.legend_elements(), loc="lower right", title="Impact",
#            fontsize=subt_font)


# lg.get_title().set_fontsize(axis_font) #legend 'Title' fontsize

fig.tight_layout()
plt.show()

#%% regression models

# Fit costs (SVR)

# fit impacted set
mdl_hit.fit_svr()
mdl_hit.fit_kernel_ridge(kernel_name='rbf')

mdl_time_hit.fit_svr()
mdl_time_hit.fit_kernel_ridge(kernel_name='rbf')

mdl_drift_hit.fit_kernel_ridge(kernel_name='rbf')
mdl_drift_hit.fit_ols_ridge()

# fit no impact set
mdl_miss.fit_svr()
mdl_miss.fit_kernel_ridge(kernel_name='rbf')

mdl_time_miss.fit_svr()
mdl_time_miss.fit_kernel_ridge(kernel_name='rbf')

mdl_drift_miss.fit_kernel_ridge(kernel_name='rbf')
mdl_drift_miss.fit_ols_ridge()

#%% plot no-impact regressions
axis_font = 20
subt_font = 18

plt.close('all')
mdl_miss.make_2D_plotting_space(100)

xx = mdl_miss.xx
yy = mdl_miss.yy
Z = mdl_miss.kr.predict(mdl_miss.X_plot)
Z = Z.reshape(xx.shape)

fig, ax = plt.subplots(subplot_kw={"projection": "3d"})
# Plot the surface.
surf = ax.plot_surface(xx, yy, Z, cmap=plt.cm.coolwarm,
                       linewidth=0, antialiased=False,
                       alpha=0.5)

ax.scatter(df_miss['gapRatio'], df_miss['RI'], df_miss[cost_var],
           c=df_miss[cost_var],
           edgecolors='k')

xlim = ax.get_xlim()
ylim = ax.get_ylim()
zlim = ax.get_zlim()
cset = ax.contour(xx, yy, Z, zdir='z', offset=-1e5, cmap='coolwarm')
cset = ax.contour(xx, yy, Z, zdir='x', offset=xlim[0], cmap='coolwarm_r')
cset = ax.contour(xx, yy, Z, zdir='y', offset=ylim[1], cmap='coolwarm')

ax.set_xlabel('Gap ratio', fontsize=axis_font)
ax.set_ylabel(r'$R_y$', fontsize=axis_font)
# ax.set_zlabel('Median loss ($)', fontsize=axis_font)
# ax.set_title('Median cost predictions given no impact (RBF kernel ridge)')
ax.set_zlim([0, 5e5])
fig.tight_layout()
plt.show()

#%% simple regressions sliced
plt.close('all')
plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
axis_font = 18
subt_font = 18
label_size = 14
import matplotlib as mpl
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 

# plt.close('all')

xvar = 'gapRatio'
yvar = 'RI'

res = 150
step = 0.01
y_bounds = [0.5, 0.5+res*step-step]
mdl_miss.make_2D_plotting_space(res, x_var=xvar, y_var=yvar,
                                y_bounds=y_bounds)

xx = mdl_miss.xx
yy = mdl_miss.yy
Z = mdl_miss.kr.predict(mdl_miss.X_plot)
Z = Z.reshape(xx.shape)

#fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
#plt.setp((ax1, ax2, ax3), yticks=np.arange(0.1, 1.1, step=0.1), ylim=[0.0, 1.0])

fig, axes = plt.subplots(1, 2, 
                         figsize=(13, 6))
ax1 = axes[0]
ax2 = axes[1]


yyy = yy[:,1]
cs = ax1.contour(xx, Z, yy, linewidths=1.1, cmap='coolwarm',
                 levels=np.arange(0.5, 2.0, step=0.1))
ax1.scatter(df_miss[xvar], df_miss[cost_var], c=df_miss[yvar],
          edgecolors='k', cmap='coolwarm')
ax1.clabel(cs, fontsize=label_size)
ax1.set_ylabel('Median repair cost', fontsize=axis_font)
ax1.set_xlabel('Gap ratio', fontsize=axis_font)
ax1.grid(visible=True)
ax1.plot(0.65, 0.5, color='navy', label=r'$R_y$')
ax1.legend(fontsize=label_size)
ax1.set_ylim([0, 5e5])

##

xvar = 'RI'
yvar = 'gapRatio'

res = 200
step = 0.01
y_bounds = [1.0, 1.0+res*step-step]

mdl_miss.make_2D_plotting_space(res, x_var=xvar, y_var=yvar,
                                y_bounds=y_bounds)

xx = mdl_miss.xx
yy = mdl_miss.yy
Z = mdl_miss.kr.predict(mdl_miss.X_plot)
Z = Z.reshape(xx.shape)

yyy = yy[:,1]
cs = ax2.contour(xx, Z, yy, linewidths=1.1, cmap='coolwarm',
                 levels=np.arange(1.0, 3.0, step=0.1))
ax2.scatter(df_miss[xvar], df_miss[cost_var], c=df_miss[yvar],
          edgecolors='k', cmap='coolwarm')
ax2.clabel(cs, fontsize=label_size)
ax2.set_xlabel(r'$R_y$', fontsize=axis_font)
ax2.grid(visible=True)
ax2.plot(0.65, 0.5, color='red', label=r'Gap ratio')
ax2.legend(fontsize=label_size, loc='upper left')
ax2.set_ylim([0, 5e5])

#%% 3d surf
plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
axis_font = 18
subt_font = 18
label_size = 12
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 
plt.close('all')

fig = plt.figure(figsize=(13, 8))

#plt.setp((ax1, ax2), xticks=np.arange(0.5, 4.0, step=0.5),
#        yticks=np.arange(0.5, 2.5, step=0.5))


#################################
xvar = 'gapRatio'
yvar = 'RI'

res = 100
step = 0.01
X_plot = mdl.make_2D_plotting_space(res, x_var=xvar, y_var=yvar)

grid_repair_time = predict_DV(X_plot,
                                     mdl.gpc,
                                     mdl_time_hit.kr,
                                     mdl_time_miss.kr,
                                     outcome=time_var)

xx = mdl.xx
yy = mdl.yy
zz = np.array(grid_repair_time)/4764.71
Z = zz.reshape(xx.shape)

ax1=fig.add_subplot(1, 2, 1, projection='3d')
surf = ax1.plot_surface(xx, yy, Z, cmap='Blues',
                       linewidth=0, antialiased=False, alpha=0.7,
                       vmin=-0.1)

ax1.scatter(df[xvar], df[yvar], df[time_var]/4764.71, color='white',
           edgecolors='k', alpha = 0.7)

xlim = ax1.get_xlim()
ylim = ax1.get_ylim()
zlim = ax1.get_zlim()
cset = ax1.contour(xx, yy, Z, zdir='z', offset=zlim[0], cmap='Blues')
cset = ax1.contour(xx, yy, Z, zdir='x', offset=xlim[0], cmap='Blues')
cset = ax1.contour(xx, yy, Z, zdir='y', offset=ylim[1], cmap='Blues')

ax1.set_xlabel('Gap ratio', fontsize=axis_font)
ax1.set_ylabel('$R_y$', fontsize=axis_font)
#ax1.set_zlabel('Median loss ($)', fontsize=axis_font)
ax1.set_title('a) Downtime: GPC-KR', fontsize=subt_font)

#################################
xvar = 'gapRatio'
yvar = 'RI'

res = 100
step = 0.01
X_plot = mdl.make_2D_plotting_space(res, x_var=xvar, y_var=yvar)

grid_repair_cost = predict_DV(X_plot,
                                     mdl.gpc,
                                     mdl_hit.kr,
                                     mdl_miss.kr,
                                     outcome=cost_var)

xx = mdl.xx
yy = mdl.yy
zz = np.array(grid_repair_cost)/8.1e6
Z = zz.reshape(xx.shape)

ax2=fig.add_subplot(1, 2, 2, projection='3d')
surf = ax2.plot_surface(xx, yy, Z, cmap='Blues',
                       linewidth=0, antialiased=False, alpha=0.7,
                       vmin=-0.1)

ax2.scatter(df[xvar], df[yvar], df[cost_var]/8.1e6, color='white',
           edgecolors='k', alpha = 0.7)

xlim = ax2.get_xlim()
ylim = ax2.get_ylim()
zlim = ax2.get_zlim()
cset = ax2.contour(xx, yy, Z, zdir='z', offset=zlim[0], cmap='Blues')
cset = ax2.contour(xx, yy, Z, zdir='x', offset=xlim[0], cmap='Blues')
cset = ax2.contour(xx, yy, Z, zdir='y', offset=ylim[1], cmap='Blues')

ax2.set_xlabel('Gap ratio', fontsize=axis_font)
ax2.set_ylabel('$R_y$', fontsize=axis_font)
ax2.set_zlabel('% of replacement cost', fontsize=axis_font)
ax2.set_title('b) Cost: GPC-KR', fontsize=subt_font)

fig.tight_layout()


#%% read out results

design_repair_cost = df_val['cost_mean'].mean()
design_repair_cost_med = df_val['cost_50%'].mean()
design_downtime = df_val['time_u_mean'].mean()
design_downtime_med = df_val['time_u_50%'].mean()
design_collapse_risk = df_val['collapse_freq'].mean()
design_replacement_risk = df_val['replacement_freq'].mean()

print('====== INVERSE DESIGN ======')
print('Estimated mean repair cost: ',
      f'${design_repair_cost:,.2f}')
print('Estimated median repair cost: ',
      f'${design_repair_cost_med:,.2f}')
print('Estimated mean repair time (sequential): ',
      f'{design_downtime:,.2f}', 'worker-days')
print('Estimated median repair time (sequential): ',
      f'{design_downtime_med:,.2f}', 'worker-days')
print('Estimated collapse frequency: ',
      f'{design_collapse_risk:.2%}')
print('Estimated replacement frequency: ',
      f'{design_replacement_risk:.2%}')

baseline_repair_cost = df_base['cost_mean'].mean()
baseline_repair_cost_med = df_base['cost_50%'].mean()
baseline_downtime = df_base['time_u_mean'].mean()
baseline_downtime_med = df_base['time_u_50%'].mean()
baseline_collapse_risk = df_base['collapse_freq'].mean()
baseline_replacement_risk = df_base['replacement_freq'].mean()

print('====== BASELINE DESIGN ======')
print('Estimated mean repair cost: ',
      f'${baseline_repair_cost:,.2f}')
print('Estimated median repair cost: ',
      f'${baseline_repair_cost_med:,.2f}')
print('Estimated mean repair time (sequential): ',
      f'{baseline_downtime:,.2f}', 'worker-days')
print('Estimated median repair time (sequential): ',
      f'{baseline_downtime_med:,.2f}', 'worker-days')
print('Estimated collapse frequency: ',
      f'{baseline_collapse_risk:.2%}')
print('Estimated replacement frequency: ',
      f'{baseline_replacement_risk:.2%}')




#%% Prediction 3ds
plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
title_font=20
axis_font = 18
subt_font = 18
label_size = 16
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 
plt.close('all')

X_plot = mdl.make_2D_plotting_space(100)
# X_plot['Tm']=3.0
# X_plot['zetaM'] = 0.15
plt_density = 200
grid_drift = predict_DV(X_plot,
                        mdl.gpc,
                        mdl_drift_hit.o_ridge,
                        mdl_drift_miss.o_ridge,
                                  outcome='max_drift')

xx = mdl.xx
yy = mdl.yy
Z = np.array(grid_drift)
Z = Z.reshape(xx.shape)

fig = plt.figure(figsize=(11, 9))
ax1=fig.add_subplot(2, 2, 1, projection='3d')

# Plot the surface.
surf = ax1.plot_surface(xx, yy, Z, cmap=plt.cm.Blues,
                       linewidth=0, antialiased=False,
                       alpha=0.7, vmin=0, vmax=0.075)

ax1.scatter(df['gapRatio'][:plt_density], df['RI'][:plt_density], 
           df['max_drift'][:plt_density],
           edgecolors='k')

ax1.set_xlabel('\nGap ratio', fontsize=axis_font, linespacing=0.5)
ax1.set_ylabel('\n$R_y$', fontsize=axis_font, linespacing=1.0)
ax1.set_zlabel('\nPID (%)', fontsize=axis_font, linespacing=3.0)
ax1.set_title('Peak interstory drift prediction', fontsize=title_font)
fig.tight_layout()
plt.show()

# drift -> collapse risk
from scipy.stats import lognorm
from math import log, exp

from scipy.stats import norm
inv_norm = norm.ppf(0.84)
beta_drift = 0.25
mean_log_drift = exp(log(0.1) - beta_drift*inv_norm) # 0.9945 is inverse normCDF of 0.84

ln_dist = lognorm(s=beta_drift, scale=mean_log_drift)

Z = ln_dist.cdf(np.array(grid_drift))
Z = Z.reshape(xx.shape)

ax2=fig.add_subplot(2, 2, 2, projection='3d')
# Plot the surface.
surf = ax2.plot_surface(xx, yy, Z*100, cmap=plt.cm.Blues,
                       linewidth=0, antialiased=False,
                       alpha=0.7, vmin=-10, vmax=70)

ax2.scatter(df['gapRatio'][:plt_density], df['RI'][:plt_density], 
           df['collapse_freq'][:plt_density]*100,
           edgecolors='k')

ax2.set_xlabel('\nGap ratio', fontsize=axis_font, linespacing=0.5)
ax2.set_ylabel('\n$R_y$', fontsize=axis_font, linespacing=1.0)
ax2.set_zlabel('\nCollapse risk (%)', fontsize=axis_font, linespacing=3.0)
ax2.set_title('Collapse risk prediction', fontsize=title_font)

#################################

grid_repair_time = predict_DV(X_plot,
                                     mdl.gpc,
                                     mdl_time_hit.kr,
                                     mdl_time_miss.kr,
                                     outcome=time_var)

xx = mdl.xx
yy = mdl.yy
zz = np.array(grid_repair_time)/4764.71
Z = zz.reshape(xx.shape)*100

ax3=fig.add_subplot(2, 2, 3, projection='3d')
surf = ax3.plot_surface(xx, yy, Z, cmap='Blues',
                       linewidth=0, antialiased=False, alpha=0.7,
                       vmin=-0.1)

ax3.scatter(df[xvar], df[yvar], df[time_var]/4764.71*100,
           edgecolors='k')

# xlim = ax3.get_xlim()
# ylim = ax3.get_ylim()
# zlim = ax3.get_zlim()
# cset = ax1.contour(xx, yy, Z, zdir='z', offset=zlim[0], cmap='Blues')
# cset = ax1.contour(xx, yy, Z, zdir='x', offset=xlim[0], cmap='Blues')
# cset = ax1.contour(xx, yy, Z, zdir='y', offset=ylim[1], cmap='Blues')

ax3.set_xlabel('\nGap ratio', fontsize=axis_font, linespacing=0.5)
ax3.set_ylabel('\n$R_y$', fontsize=axis_font, linespacing=1.0)
ax3.set_zlabel('\n% of replacement time', fontsize=axis_font, linespacing=3.0)
ax3.set_title('\nDowntime prediction', fontsize=title_font, linespacing=0.5)

#################################

grid_repair_cost = predict_DV(X_plot,
                                     mdl.gpc,
                                     mdl_hit.kr,
                                     mdl_miss.kr,
                                     outcome=cost_var)

xx = mdl.xx
yy = mdl.yy
zz = np.array(grid_repair_cost)/8.1e6
Z = zz.reshape(xx.shape)*100.

ax4=fig.add_subplot(2, 2, 4, projection='3d')

surf = ax4.plot_surface(xx, yy, Z, cmap='Blues',
                       linewidth=0, antialiased=False, alpha=0.7,
                       vmin=-0.1)

ax4.scatter(df[xvar], df[yvar], df[cost_var]/8.1e6*100,
           edgecolors='k')

# xlim = ax2.get_xlim()
# ylim = ax2.get_ylim()
# zlim = ax2.get_zlim()
# cset = ax2.contour(xx, yy, Z, zdir='z', offset=zlim[0], cmap='Blues')
# cset = ax2.contour(xx, yy, Z, zdir='x', offset=xlim[0], cmap='Blues')
# cset = ax2.contour(xx, yy, Z, zdir='y', offset=ylim[1], cmap='Blues')

ax4.set_xlabel('\nGap ratio', fontsize=axis_font, linespacing=0.5)
ax4.set_ylabel('\n$R_y$', fontsize=axis_font, linespacing=1.0)
ax4.set_zlabel('\n% of replacement cost', fontsize=axis_font, linespacing=3.0)
ax4.set_title('Repair cost', fontsize=title_font)

fig.tight_layout(w_pad=0.0)
plt.show()


#%% dirty contours

plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
title_font=20
axis_font = 18
subt_font = 15
label_size = 16
clabel_size = 12
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 
plt.close('all')

import numpy as np
# x is gap, y is Ry
x_var = 'gapRatio'
y_var = 'RI'
third_var = 'Tm'
fourth_var = 'zetaM'
x_min = 0.3
x_max = 2.5
y_min = 0.5
y_max = 2.0

lvls = np.array([0.025, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5])

res = 200

xx, yy = np.meshgrid(np.linspace(x_min,
                                 x_max,
                                 res),
                     np.linspace(y_min,
                                 y_max,
                                 res))

X_pl = pd.DataFrame({x_var:xx.ravel(),
                     y_var:yy.ravel(),
                     third_var:np.repeat(2.5,
                                         res*res),
                     fourth_var:np.repeat(0.15,
                                          res*res)})

X_plot = X_pl[['gapRatio', 'RI', 'Tm', 'zetaM']]

grid_drift = predict_DV(X_plot,
                        mdl.gpc,
                        mdl_drift_hit.o_ridge,
                        mdl_drift_miss.o_ridge,
                                  outcome='max_drift')


# drift -> collapse risk
from scipy.stats import lognorm
from math import log, exp

from scipy.stats import norm
inv_norm = norm.ppf(0.84)
beta_drift = 0.25
mean_log_drift = exp(log(0.1) - beta_drift*inv_norm) # 0.9945 is inverse normCDF of 0.84

ln_dist = lognorm(s=beta_drift, scale=mean_log_drift)

Z = ln_dist.cdf(np.array(grid_drift))
Z = Z.reshape(xx.shape)

fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(14, 4.5))
plt.setp((ax1, ax2, ax3), xticks=np.arange(0.5, 4.0, step=0.5))

cs = ax1.contour(xx, yy, Z, linewidths=1.1, cmap='Blues', vmin=-1,
                 levels=lvls)

probDes = 0.1
from scipy.interpolate import RegularGridInterpolator
RyList = [1.0, 2.0]
for j in range(len(RyList)):
    RyTest = RyList[j]
    lpBox = Z
    xq = np.linspace(0.3, 1.8, 200)
    
    interp = RegularGridInterpolator((yy[:,0], xx[0,:]), lpBox)
    pts = np.zeros((200,2))
    pts[:,1] = xq
    pts[:,0] = RyTest
    lq = interp(pts)
    
    theGapIdx = np.argmin(abs(lq - probDes))
    theGap = xq[theGapIdx]
    ax1.vlines(x=theGap, ymin=0.49, ymax=RyTest, color='red')
    ax1.hlines(y=RyTest, xmin=0.3, xmax=theGap, color='red')
    ax1.text(theGap+0.05, 0.5, r'GR = '+f'{theGap:,.2f}', rotation=90,
             fontsize=subt_font, color='red')
    ax1.plot([theGap], [RyTest], marker='*', markersize=15, color="red")

df_sc = df[(df['Tm']<=2.65) & (df['zetaM']<=0.17) & (df['zetaM']>=0.13)]

ax1.scatter(df_sc[x_var],
            df_sc[y_var],
            c=df_sc['collapse_probs'], cmap='Blues',
            s=30, edgecolors='k')

ax1.clabel(cs, fontsize=clabel_size)

ax1.contour(xx, yy, Z, levels = [0.1], colors=('red'),
            linestyles=('-'),linewidths=(2,))

ax1.set_xlim([0.3, 2.0])
ax1.set_ylim([0.49, 2.01])


ax1.grid(visible=True)
ax1.set_title(r'$T_M = 2.00$ s, $\zeta_M = 0.15$', fontsize=title_font)
ax1.set_xlabel(r'Gap ratio (GR)', fontsize=axis_font)
ax1.set_ylabel(r'$R_y$', fontsize=axis_font)


#####
x_var = 'gapRatio'
y_var = 'RI'
third_var = 'Tm'
fourth_var = 'zetaM'
x_min = 0.3
x_max = 2.5
y_min = 0.5
y_max = 2.0

xx, yy = np.meshgrid(np.linspace(x_min,
                                 x_max,
                                 res),
                     np.linspace(y_min,
                                 y_max,
                                 res))

X_pl = pd.DataFrame({x_var:xx.ravel(),
                     y_var:yy.ravel(),
                     third_var:np.repeat(3.25,
                                         res*res),
                     fourth_var:np.repeat(0.15,
                                          res*res)})

X_plot = X_pl[['gapRatio', 'RI', 'Tm', 'zetaM']]

grid_drift = predict_DV(X_plot,
                        mdl.gpc,
                        mdl_drift_hit.o_ridge,
                        mdl_drift_miss.o_ridge,
                                  outcome='max_drift')


# drift -> collapse risk
from scipy.stats import lognorm
from math import log, exp

from scipy.stats import norm
inv_norm = norm.ppf(0.84)
beta_drift = 0.25
mean_log_drift = exp(log(0.1) - beta_drift*inv_norm) # 0.9945 is inverse normCDF of 0.84

ln_dist = lognorm(s=beta_drift, scale=mean_log_drift)

Z = ln_dist.cdf(np.array(grid_drift))
Z = Z.reshape(xx.shape)

cs = ax2.contour(xx, yy, Z, linewidths=1.1, cmap='Blues', vmin=-1,
                 levels=lvls)

from scipy.interpolate import RegularGridInterpolator
RyList = [1.0, 2.0]
for j in range(len(RyList)):
    RyTest = RyList[j]
    lpBox = Z
    xq = np.linspace(0.3, 1.8, 200)
    
    interp = RegularGridInterpolator((yy[:,0], xx[0,:]), lpBox)
    pts = np.zeros((200,2))
    pts[:,1] = xq
    pts[:,0] = RyTest
    lq = interp(pts)
    theGapIdx = np.argmin(abs(lq - probDes))
    theGap = xq[theGapIdx]
    ax2.vlines(x=theGap, ymin=0.49, ymax=RyTest, color='red')
    ax2.hlines(y=RyTest, xmin=0.3, xmax=theGap, color='red')
    ax2.text(theGap+0.05, 0.5, r'GR = '+f'{theGap:,.2f}', rotation=90,
             fontsize=subt_font, color='red')
    ax2.plot([theGap], [RyTest], marker='*', markersize=15, color="red")
    
ax2.clabel(cs, fontsize=clabel_size)

ax2.contour(xx, yy, Z, levels = [0.1], colors=('red'),
            linestyles=('-'),linewidths=(2,))

ax2.set_xlim([0.3, 2.0])
ax2.set_ylim([0.49, 2.01])

df_sc = df[(df['Tm']<=3.4) & (df['Tm']>=3.1) & (df['zetaM']<=0.17) & (df['zetaM']>=0.13)]

ax2.scatter(df_sc[x_var],
            df_sc[y_var],
            c=df_sc['collapse_probs'], cmap='Blues',
            s=30, edgecolors='k')

ax2.grid(visible=True)
ax2.set_title(r'$T_M = 3.25$ s, $\zeta_M = 0.15$', fontsize=title_font)
ax2.set_xlabel(r'Gap ratio (GR)', fontsize=axis_font)
ax2.set_ylabel(r'$R_y$', fontsize=axis_font)
#####
x_var = 'gapRatio'
y_var = 'RI'
third_var = 'Tm'
fourth_var = 'zetaM'
x_min = 0.3
x_max = 2.5
y_min = 0.5
y_max = 2.0

xx, yy = np.meshgrid(np.linspace(x_min,
                                 x_max,
                                 res),
                     np.linspace(y_min,
                                 y_max,
                                 res))

X_pl = pd.DataFrame({x_var:xx.ravel(),
                     y_var:yy.ravel(),
                     third_var:np.repeat(4.0,
                                         res*res),
                     fourth_var:np.repeat(0.15,
                                          res*res)})

X_plot = X_pl[['gapRatio', 'RI', 'Tm', 'zetaM']]

grid_drift = predict_DV(X_plot,
                        mdl.gpc,
                        mdl_drift_hit.o_ridge,
                        mdl_drift_miss.o_ridge,
                                  outcome='max_drift')


# drift -> collapse risk
from scipy.stats import lognorm
from math import log, exp

from scipy.stats import norm
inv_norm = norm.ppf(0.84)
beta_drift = 0.25
mean_log_drift = exp(log(0.1) - beta_drift*inv_norm) # 0.9945 is inverse normCDF of 0.84

ln_dist = lognorm(s=beta_drift, scale=mean_log_drift)

Z = ln_dist.cdf(np.array(grid_drift))
Z = Z.reshape(xx.shape)

cs = ax3.contour(xx, yy, Z, linewidths=1.1, cmap='Blues', vmin=-1,
                 levels=lvls)

from scipy.interpolate import RegularGridInterpolator
RyList = [0.5, 1.0, 2.0]
for j in range(len(RyList)):
    RyTest = RyList[j]
    lpBox = Z
    xq = np.linspace(0.3, 1.8, 200)
    
    interp = RegularGridInterpolator((yy[:,0], xx[0,:]), lpBox)
    pts = np.zeros((200,2))
    pts[:,1] = xq
    pts[:,0] = RyTest
    lq = interp(pts)
    theGapIdx = np.argmin(abs(lq - probDes))
    theGap = xq[theGapIdx]
    ax3.vlines(x=theGap, ymin=0.49, ymax=RyTest, color='red')
    ax3.hlines(y=RyTest, xmin=0.3, xmax=theGap, color='red')
    ax3.text(theGap+0.05, 0.5, r'GR = '+f'{theGap:,.2f}', rotation=90,
             fontsize=subt_font, color='red')
    ax3.plot([theGap], [RyTest], marker='*', markersize=15, color="red")

ax3.clabel(cs, fontsize=clabel_size)

ax3.contour(xx, yy, Z, levels = [0.1], colors=('red'),
            linestyles=('-'),linewidths=(2,))

ax3.set_xlim([0.3, 2.0])
ax3.set_ylim([0.49, 2.01])

df_sc = df[(df['Tm']>=3.80) & (df['zetaM']<=0.17) & (df['zetaM']>=0.13)]

sc = ax3.scatter(df_sc[x_var],
            df_sc[y_var],
            c=df_sc['collapse_probs'], cmap='Blues',
            s=30, edgecolors='k')

ax3.grid(visible=True)
ax3.set_title(r'$T_M = 4.0$ s, $\zeta_M = 0.15$', fontsize=title_font)
ax3.set_xlabel(r'Gap ratio (GR)', fontsize=axis_font)
ax3.set_ylabel(r'$R_y$', fontsize=axis_font)

handles, labels = sc.legend_elements(prop="colors", alpha=0.6)
legend2 = ax3.legend(handles, labels, loc="lower right", title="% collapse",
                     fontsize=subt_font, title_fontsize=subt_font)

fig.tight_layout()

#%% dirty contours (probability edition)

plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
title_font=20
axis_font = 18
subt_font = 18
label_size = 16
clabel_size = 14
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 
plt.close('all')

import numpy as np
# x is gap, y is Ry
x_var = 'gapRatio'
y_var = 'RI'
third_var = 'Tm'
fourth_var = 'zetaM'
x_min = 0.3
x_max = 2.5
y_min = 0.5
y_max = 2.0

lvls = np.array([0.025, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5])

res = 200

xx, yy = np.meshgrid(np.linspace(x_min,
                                 x_max,
                                 res),
                     np.linspace(y_min,
                                 y_max,
                                 res))

X_pl = pd.DataFrame({x_var:xx.ravel(),
                     y_var:yy.ravel(),
                     third_var:np.repeat(3.0,
                                         res*res),
                     fourth_var:np.repeat(0.15,
                                          res*res)})

X_plot = X_pl[['gapRatio', 'RI', 'Tm', 'zetaM']]

grid_drift = predict_DV(X_plot,
                        mdl.gpc,
                        mdl_drift_hit.o_ridge,
                        mdl_drift_miss.o_ridge,
                                  outcome='max_drift')


# drift -> collapse risk
from scipy.stats import lognorm
from math import log, exp

from scipy.stats import norm
inv_norm = norm.ppf(0.84)
beta_drift = 0.25
mean_log_drift = exp(log(0.1) - beta_drift*inv_norm) # 0.9945 is inverse normCDF of 0.84

ln_dist = lognorm(s=beta_drift, scale=mean_log_drift)

Z = ln_dist.cdf(np.array(grid_drift))
Z = Z.reshape(xx.shape)

fig, ax1 = plt.subplots(1, 1, figsize=(8, 6))

cs = ax1.contour(xx, yy, Z, linewidths=1.1, cmap='Blues', vmin=-1,
                 levels=lvls)


prob_list = [0.025, 0.05, 0.1]
offset_list = [1.03, 0.93, 0.85]
color_list = ['red', 'red', 'red']
from scipy.interpolate import RegularGridInterpolator
for j, prob_des in enumerate(prob_list):
    lpBox = Z
    xq = np.linspace(0.3, 1.8, 200)
    
    interp = RegularGridInterpolator((yy[:,0], xx[0,:]), lpBox)
    pts = np.zeros((200,2))
    pts[:,1] = xq
    pts[:,0] = 1.0
    lq = interp(pts)
    
    theGapIdx = np.argmin(abs(lq - prob_des))
    
    theGap = xq[theGapIdx]
    
    ax1.vlines(x=theGap, ymin=0.49, ymax=1.0, color=color_list[j],
               linewidth=2.0)
    ax1.hlines(y=1.0, xmin=0.5, xmax=theGap, color='red', linewidth=2.0)
    ax1.text(offset_list[j], 0.75, r'GR = '+f'{theGap:,.2f}', rotation=90,
             fontsize=subt_font, color=color_list[j])
    ax1.plot([theGap], [1.0], marker='*', markersize=15, color=color_list[j])


df_sc = df[(df['Tm']>=2.8) & (df['Tm']<=3.2) & 
           (df['zetaM']<=0.17) & (df['zetaM']>=0.13)]

ax1.scatter(df_sc[x_var],
            df_sc[y_var],
            c=df_sc['collapse_probs'], cmap='Blues',
            s=30, edgecolors='k')

ax1.clabel(cs, fontsize=clabel_size)
ax1.set_xlim([0.75, 1.3])
ax1.set_ylim([0.75, 1.5])


ax1.grid(visible=True)
ax1.set_title(r'$T_M = 3.00$ s, $\zeta_M = 0.15$', fontsize=title_font)
ax1.set_xlabel(r'Gap ratio (GR)', fontsize=axis_font)
ax1.set_ylabel(r'$R_y$', fontsize=axis_font)

handles, labels = sc.legend_elements(prop="colors", alpha=0.6)
legend2 = ax1.legend(handles, labels, loc="lower right", title="% collapse",
                     fontsize=subt_font, title_fontsize=subt_font)

# ax1.contour(xx, yy, Z, levels = prob_list, colors=('red', 'brown', 'black'),
#             linestyles=('-'),linewidths=(2,))

#%% dirty contours (downtime edition)

plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
title_font=20
axis_font = 18
subt_font = 18
label_size = 16
clabel_size = 14
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 
plt.close('all')

import numpy as np
# x is gap, y is Ry
x_var = 'gapRatio'
y_var = 'Tm'
third_var = 'RI'
fourth_var = 'zetaM'
x_min = 0.3
x_max = 3.0
y_min = 2.5
y_max = 4.0

lvls = np.array([7., 14., 21., 28., 56.])

res = 200

xx, yy = np.meshgrid(np.linspace(x_min,
                                 x_max,
                                 res),
                     np.linspace(y_min,
                                 y_max,
                                 res))

X_pl = pd.DataFrame({x_var:xx.ravel(),
                     y_var:yy.ravel(),
                     third_var:np.repeat(2.0,
                                         res*res),
                     fourth_var:np.repeat(0.2,
                                          res*res)})

X_plot = X_pl[['gapRatio', 'RI', 'Tm', 'zetaM']]

grid_repair_time = predict_DV(X_plot,
                                     mdl.gpc,
                                     mdl_time_hit.kr,
                                     mdl_time_miss.kr,
                                     outcome=time_var)

zz = np.array(grid_repair_time)/50.0
Z = zz.reshape(xx.shape)

fig, ax1 = plt.subplots(1, 1, figsize=(8, 6))

cs = ax1.contour(xx, yy, Z, linewidths=1.1, cmap='Blues', vmin=-50,
                 levels=lvls)


dt_list = [7., 14., 28.]
offset_list = [1.03, 0.93, 0.85]
color_list = ['red', 'brown', 'black']
fixed_Ry = 3.5
from scipy.interpolate import RegularGridInterpolator
for j, days in enumerate(dt_list):
    lpBox = Z
    xq = np.linspace(0.5, 3.0, 200)
    
    interp = RegularGridInterpolator((yy[:,0], xx[0,:]), lpBox)
    pts = np.zeros((200,2))
    pts[:,1] = xq
    pts[:,0] = fixed_Ry
    lq = interp(pts)
    
    theGapIdx = np.argmin(abs(lq - days))
    
    theGap = xq[theGapIdx]
    
    ax1.vlines(x=theGap, ymin=0.49, ymax=fixed_Ry, color=color_list[j],
                linewidth=2.0)
    ax1.text(offset_list[j], 2.5, r'GR = '+f'{theGap:,.2f}', rotation=90,
              fontsize=subt_font, color=color_list[j])
    ax1.plot([theGap], [fixed_Ry], marker='*', markersize=15, color=color_list[j])

# df_sc = df[(df['Tm']>=2.8) & (df['Tm']<=3.2) & 
#            (df['zetaM']<=0.17) & (df['zetaM']>=0.13)]

# ax1.scatter(df_sc[x_var],
#             df_sc[y_var],
#             c=df_sc['collapse_probs'], cmap='Blues',
#             s=30, edgecolors='k')

ax1.clabel(cs, fontsize=clabel_size)
ax1.set_xlim([0.5, 3.0])
ax1.set_ylim([2.5, 4.0])


ax1.grid(visible=True)
ax1.set_title(r'$R_y = 2.00$ s, $\zeta_M = 0.20$', fontsize=title_font)
ax1.set_xlabel(r'Gap ratio (GR)', fontsize=axis_font)
ax1.set_ylabel(r'$T_M$', fontsize=axis_font)

# handles, labels = sc.legend_elements(prop="colors", alpha=0.6)
# legend2 = ax1.legend(handles, labels, loc="lower right", title="% collapse",
#                      fontsize=subt_font)

#%% filter design graphic
## start with the probability graph

plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
title_font=20
axis_font = 18
subt_font = 12
label_size = 16
clabel_size = 14
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 
plt.close('all')

import numpy as np
# x is gap, y is Ry
x_var = 'gapRatio'
y_var = 'RI'
third_var = 'Tm'
fourth_var = 'zetaM'
x_min = 0.3
x_max = 2.5
y_min = 0.5
y_max = 2.0

lvls = np.array([0, 0.025, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01])

res = 200

xx, yy = np.meshgrid(np.linspace(x_min,
                                 x_max,
                                 res),
                     np.linspace(y_min,
                                 y_max,
                                 res))

X_pl = pd.DataFrame({x_var:xx.ravel(),
                     y_var:yy.ravel(),
                     third_var:np.repeat(3.0,
                                         res*res),
                     fourth_var:np.repeat(0.15,
                                          res*res)})

X_plot = X_pl[['gapRatio', 'RI', 'Tm', 'zetaM']]

grid_drift = predict_DV(X_plot,
                        mdl.gpc,
                        mdl_drift_hit.o_ridge,
                        mdl_drift_miss.o_ridge,
                                  outcome='max_drift')


# drift -> collapse risk
from scipy.stats import lognorm
from math import log, exp

from scipy.stats import norm
inv_norm = norm.ppf(0.84)
beta_drift = 0.25
mean_log_drift = exp(log(0.1) - beta_drift*inv_norm) # 0.9945 is inverse normCDF of 0.84

ln_dist = lognorm(s=beta_drift, scale=mean_log_drift)

Z = ln_dist.cdf(np.array(grid_drift))
Z = Z.reshape(xx.shape)

fig = plt.figure(figsize=(13, 9))
ax1 = fig.add_subplot(2, 2, 1)

cs = ax1.contour(xx, yy, Z, linewidths=1.1, cmap='Blues', 
                 levels=lvls, vmin=-.1, legend='brief')

nm, lbl = cs.legend_elements()
lbl = ['% collapse']
plt.legend(nm, lbl, title= '', fontsize= subt_font) 

prob_list = [0.025, 0.05, 0.1]
offset_list = [1.03, 0.93, 0.85]
color_list = ['red', 'brown', 'black']
from scipy.interpolate import RegularGridInterpolator


ax1.clabel(cs, fontsize=clabel_size, colors='black')
ax1.set_xlim([0.5, 2.5])
ax1.set_ylim([0.5, 2.0])


ax1.grid(visible=True)
ax1.set_title('Collapse risk < 2.5%', fontsize=title_font)
ax1.set_xlabel(r'Gap ratio (GR)', fontsize=axis_font)
ax1.set_ylabel(r'$R_y$', fontsize=axis_font)

cs = ax1.contour(xx, yy, Z, levels = [0.025], colors=('red'),
            linestyles=('-'),linewidths=(2,))
ax1.clabel(cs, fontsize=clabel_size, colors='red')



## now we do cost
grid_repair_cost = predict_DV(X_plot,
                                     mdl.gpc,
                                     mdl_hit.kr,
                                     mdl_miss.kr,
                                     outcome=cost_var)

zz = np.array(grid_repair_cost)/8.1e6
Z_cost = zz.reshape(xx.shape)


ax2 = fig.add_subplot(2, 2, 2)


lvls=[0.0, 0.025, 1.0]
cs = ax2.contourf(xx, yy, Z, linewidths=1.1, cmap='Greys', levels=lvls)

cs = ax2.contour(xx, yy, Z, levels = [0.025], colors=('black'),
            linestyles=('--'),linewidths=(2,))
ax2.clabel(cs, fontsize=clabel_size, colors='black')

lvls = np.arange(0.0, 1.0, 0.1)
cs = ax2.contour(xx, yy, Z_cost, linewidths=1.1, cmap='Blues', 
                 levels=lvls, vmin=-0.1)
ax2.clabel(cs, fontsize=clabel_size, colors='black')

nm, lbl = cs.legend_elements()
lbl = ['% replacement cost']
plt.legend(nm, lbl, title= '', fontsize= subt_font) 


cs = ax2.contour(xx, yy, Z_cost, levels = [0.2], colors=('red'),
            linestyles=('-'),linewidths=(2,))
ax2.clabel(cs, fontsize=clabel_size, colors='red')

ax2.grid(visible=True)
ax2.set_title('Repair cost <20% replacement', fontsize=title_font)
ax2.set_xlabel(r'Gap ratio (GR)', fontsize=axis_font)
ax2.set_ylabel(r'$R_y$', fontsize=axis_font)
ax2.set_xlim([0.5, 2.5])
ax2.set_ylim([0.5, 2.0])


## now we do time
grid_repair_time = predict_DV(X_plot,
                                     mdl.gpc,
                                     mdl_time_hit.kr,
                                     mdl_time_miss.kr,
                                     outcome=time_var)

zz = np.array(grid_repair_time)/50.0
Z_time = zz.reshape(xx.shape)

ax3 = fig.add_subplot(2, 2, 3)

lvls=[-0.01, 0.2, 1.1]
cs = ax3.contourf(xx, yy, Z_cost, linewidths=1.1, cmap='Greys', levels=lvls)

cs = ax3.contour(xx, yy, Z_cost, levels = [0.2], colors=('black'),
            linestyles=('--'),linewidths=(2,))
ax3.clabel(cs, fontsize=clabel_size, colors='black')

lvls = [7.0, 14.0, 21., 28., 35., 42., 49.]
cs = ax3.contour(xx, yy, Z_time, linewidths=1.1, cmap='Blues', 
                 levels=lvls, vmin=-20)
ax3.clabel(cs, fontsize=clabel_size, colors='black')
nm, lbl = cs.legend_elements()
lbl = ['Days (50 workers)']
plt.legend(nm, lbl, title= '', fontsize= subt_font) 



cs = ax3.contour(xx, yy, Z_time, levels = [14.], colors=('red'),
            linestyles=('-'),linewidths=(2,))
ax3.clabel(cs, fontsize=clabel_size, colors='red')

ax3.grid(visible=True)
ax3.set_title('Repair time < 14 days', fontsize=title_font)
ax3.set_xlabel(r'Gap ratio (GR)', fontsize=axis_font)
ax3.set_ylabel(r'$R_y$', fontsize=axis_font)
ax3.set_xlim([0.5, 2.5])
ax3.set_ylim([0.5, 2.0])

ax4 = fig.add_subplot(2, 2, 4)

lvls=[-0.01, 14, 1000.0]
cs = ax4.contourf(xx, yy, Z_time, linewidths=1.1, cmap='Greys', levels=lvls)

cs = ax4.contour(xx, yy, Z_time, levels = [14], colors=('black'),
            linestyles=('--'),linewidths=(2,))
ax4.clabel(cs, fontsize=clabel_size, colors='black')

ax4.grid(visible=True)
ax4.set_title('Acceptable design space', fontsize=title_font)
ax4.set_xlabel(r'Gap ratio (GR)', fontsize=axis_font)
ax4.set_ylabel(r'$R_y$', fontsize=axis_font)
ax4.set_xlim([0.5, 2.5])
ax4.set_ylim([0.5, 2.0])

ax2.text(1.75, 1.25, 'OK space',
          fontsize=axis_font, color='green')

ax3.text(1.75, 1.25, 'OK space',
          fontsize=axis_font, color='green')

ax4.text(1.75, 1.25, 'OK space',
          fontsize=axis_font, color='green')

fig.tight_layout()

#%% Testing the design space
# TODO: MOVE PAST GRID SPACE DESIGN

import time

res_des = 20
X_space = mdl.make_design_space(res_des)
#K_space = mdl.get_kernel(X_space, kernel_name='rbf', gamma=gam)

# choice SVC for impact bc fast and behavior most closely resembles GPC
# HOWEVER, SVC is poorly calibrated for probablities
# consider using GP if computational resources allow, and GP looks good

# choice KR bc behavior most closely resembles GPR
# also trend is visible: impact set looks like GPR, nonimpact set favors high R
t0 = time.time()
space_repair_cost = predict_DV(X_space,
                                      mdl.gpc,
                                      mdl_hit.kr,
                                      mdl_miss.kr,
                                      outcome=cost_var)
tp = time.time() - t0
print("GPC-KR repair cost prediction for %d inputs in %.3f s" % (X_space.shape[0],
                                                           tp))

# choice KR bc smoother when predicting downtime
t0 = time.time()
space_downtime = predict_DV(X_space,
                                      mdl.gpc,
                                      mdl_time_hit.kr,
                                      mdl_time_miss.kr,
                                      outcome=time_var)
tp = time.time() - t0
print("GPC-KR downtime prediction for %d inputs in %.3f s" % (X_space.shape[0],
                                                               tp))

# choice O_ridge bc SVR seems to hang, and KR overestimates (may need CV)
t0 = time.time()
space_drift = predict_DV(X_space,
                                      mdl.gpc,
                                      mdl_drift_hit.o_ridge,
                                      mdl_drift_miss.o_ridge,
                                      outcome='max_drift')
tp = time.time() - t0
print("GPC-OR drift prediction for %d inputs in %.3f s" % (X_space.shape[0],
                                                               tp))

# Transform predicted drift into probability

# drift -> collapse risk
from scipy.stats import lognorm
from math import log, exp

from scipy.stats import norm
inv_norm = norm.ppf(0.84)
beta_drift = 0.25
mean_log_drift = exp(log(0.1) - beta_drift*inv_norm) # 0.9945 is inverse normCDF of 0.84

ln_dist = lognorm(s=beta_drift, scale=mean_log_drift)

space_collapse_risk = pd.DataFrame(ln_dist.cdf(space_drift),
                                          columns=['collapse_risk_pred'])

#%% baseline predictions
from scipy.stats import lognorm
from math import log, exp

from scipy.stats import norm
inv_norm = norm.ppf(0.84)
beta_drift = 0.25
mean_log_drift = exp(log(0.1) - beta_drift*inv_norm) # 0.9945 is inverse normCDF of 0.84

X_baseline = pd.DataFrame(np.array([[1.0, 2.0, 3.0, 0.15]]),
                          columns=['gapRatio', 'RI', 'Tm', 'zetaM'])
baseline_repair_cost = predict_DV(X_baseline,
                                      mdl.gpc,
                                      mdl_hit.kr,
                                      mdl_miss.kr,
                                      outcome=cost_var)
baseline_downtime = predict_DV(X_baseline,
                                      mdl.gpc,
                                      mdl_time_hit.kr,
                                      mdl_time_miss.kr,
                                      outcome=time_var)
baseline_drift = predict_DV(X_baseline,
                                      mdl.gpc,
                                      mdl_drift_hit.o_ridge,
                                      mdl_drift_miss.o_ridge,
                                      outcome='max_drift')

baseline_collapse_risk = ln_dist.cdf(baseline_drift)


#%% refine space to meet repair cost and downtime requirements
plt.close('all')
steel_price = 2.00
coef_dict = get_steel_coefs(df, steel_per_unit=steel_price)

percent_of_replacement = 0.2
cost_thresh = percent_of_replacement*8.1e6
ok_cost = X_space.loc[space_repair_cost[cost_var+'_pred']<=cost_thresh]

# <2 weeks for a team of 50
dt_thresh = 50*14
ok_time = X_space.loc[space_downtime[time_var+'_pred']<=dt_thresh]

risk_thresh = 0.025
ok_risk = X_space.loc[space_collapse_risk['collapse_risk_pred']<=
                      risk_thresh]

X_design = X_space[np.logical_and.reduce((
        X_space.index.isin(ok_cost.index), 
        X_space.index.isin(ok_time.index),
        X_space.index.isin(ok_risk.index)))]
    
# in the filter-design process, only one of cost/dt is likely to control
    
# TODO: more clever selection criteria (not necessarily the cheapest)

# select best viable design
upfront_costs = calc_upfront_cost(X_design, coef_dict)
cheapest_design_idx = upfront_costs.idxmin()
design_upfront_cost = upfront_costs.min()

# least upfront cost of the viable designs
best_design = X_design.loc[cheapest_design_idx]
design_downtime = space_downtime.iloc[cheapest_design_idx].item()
design_repair_cost = space_repair_cost.iloc[cheapest_design_idx].item()
design_collapse_risk = space_collapse_risk.iloc[cheapest_design_idx].item()
design_PID = space_drift.iloc[cheapest_design_idx].item()

print(best_design)

print('Upfront cost of selected design: ',
      f'${design_upfront_cost:,.2f}')
print('Predicted median repair cost: ',
      f'${design_repair_cost:,.2f}')
print('Predicted repair time (sequential): ',
      f'{design_downtime:,.2f}', 'worker-days')
print('Predicted collapse risk: ',
      f'{design_collapse_risk:.2%}')
print('Predicted peak interstory drift: ',
      f'{design_PID:.2%}')




#%% cost sens
land_costs = [2151., 3227., 4303., 5379.]
steel_costs = [1., 2., 3., 4.]

import numpy as np
gap_price_grid = np.zeros([4,4])
Ry_price_grid = np.zeros([4,4])
Tm_price_grid = np.zeros([4,4])
zetaM_price_grid = np.zeros([4,4])
moat_price_grid = np.zeros([4,4])

percent_of_replacement = 1.0
cost_thresh = percent_of_replacement*8.1e6
ok_cost = X_space.loc[space_repair_cost[cost_var+'_pred']<=cost_thresh]

# <2 weeks for a team of 50
dt_thresh = 1e6
ok_time = X_space.loc[space_downtime[time_var+'_pred']<=dt_thresh]

# risk_thresh = 0.025
# ok_risk = X_space.loc[space_collapse_risk['collapse_risk_pred']<=
#                       risk_thresh]

risk_thresh = 0.025
ok_risk = X_space.loc[space_drift['max_drift_pred']<=
                      risk_thresh]

X_design = X_space[np.logical_and.reduce((
        X_space.index.isin(ok_cost.index), 
        X_space.index.isin(ok_time.index),
        X_space.index.isin(ok_risk.index)))]

for idx_l, land in enumerate(land_costs):
    for idx_s, steel in enumerate(steel_costs):
        steel_price = steel
        coef_dict = get_steel_coefs(df, steel_per_unit=steel_price)
        
        lcps = land/(3.28**2)
        upfront_costs = calc_upfront_cost(X_design, coef_dict, 
                                          land_cost_per_sqft=lcps)
        
        cheapest_design_idx = upfront_costs.idxmin()
        design_upfront_cost = upfront_costs.min()

        # least upfront cost of the viable designs
        best_design = X_design.loc[cheapest_design_idx]
        gap_price_grid[idx_l][idx_s] = best_design['gapRatio']
        Ry_price_grid[idx_l][idx_s] = best_design['RI']
        Tm_price_grid[idx_l][idx_s] = best_design['Tm']
        zetaM_price_grid[idx_l][idx_s] = best_design['zetaM']

        from numpy import interp
        # from ASCE Ch. 17, get damping multiplier
        zetaRef = [0.02, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50]
        BmRef   = [0.8, 1.0, 1.2, 1.5, 1.7, 1.9, 2.0]
        
        B_m = interp(best_design['zetaM'], zetaRef, BmRef)
        
        # design displacement
        g = 386.4
        pi = 3.14159
        moat_price_grid[idx_l][idx_s] = (g*1.017*best_design['Tm']/
                                         (4*pi**2*B_m)*best_design['gapRatio'])

plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
axis_font = 18
subt_font = 18
label_size = 16
import matplotlib as mpl
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 

steel_rows = ['$1.00', '$2.00', '$3.00', '$4.00']
land_cols=['$200', '$300', '$400', '$500', ]
# print(gap_price_grid)
# print(Ry_price_grid)
# print(Tm_price_grid)
# print(zetaM_price_grid)

gap_df = pd.DataFrame(data=gap_price_grid,
                      index=land_cols,
                      columns=steel_rows)

Ry_df = pd.DataFrame(data=Ry_price_grid,
                      index=land_cols,
                      columns=steel_rows)

Tm_df = pd.DataFrame(data=Tm_price_grid,
                      index=land_cols,
                      columns=steel_rows)

moat_df = pd.DataFrame(data=moat_price_grid,
                      index=land_cols,
                      columns=steel_rows)

# Draw a heatmap with the numeric values in each cell
import matplotlib.pyplot as plt
import seaborn as sns

plt.close('all')
fig, axs = plt.subplots(2, 2, figsize=(13, 9))
ax1 = axs[0][0]
ax2 = axs[0][1]
ax3 = axs[1][0]
ax4 = axs[1][1]

sns.heatmap(gap_df, annot=True, fmt='.3g', cmap='Blues', cbar=False,
            linewidths=.5, ax=ax1,  annot_kws={'size': 18})
ax1.set_ylabel('Land cost per sq ft.', fontsize=axis_font)
ax1.set_title('Gap ratio', fontsize=subt_font)

sns.heatmap(Ry_df, annot=True, fmt='.3g', cmap='Blues', cbar=False,
            linewidths=.5, ax=ax2, yticklabels=False,  annot_kws={'size': 18})
ax2.set_title(r'$R_y$', fontsize=subt_font)

sns.heatmap(Tm_df, annot=True, fmt='.3g', cmap='Blues', cbar=False,
            linewidths=.5, ax=ax3,  annot_kws={'size': 18})
ax3.set_xlabel('Steel cost per lb.', fontsize=axis_font)
ax3.set_title(r'$T_M$ (s)', fontsize=subt_font)
ax3.set_ylabel('Land cost per sq ft.', fontsize=axis_font)
fig.tight_layout()

sns.heatmap(moat_df, annot=True, fmt='.3g', cmap='Blues', cbar=False,
            linewidths=.5, ax=ax4, yticklabels=False,  annot_kws={'size': 18})
ax4.set_xlabel('Steel cost per lb.', fontsize=axis_font)
ax4.set_title(r'Moat gap (in)', fontsize=subt_font)
fig.tight_layout()

#%% only 3 design (downtime plotting)

res = 50

xx, yy, uu = np.meshgrid(np.linspace(0.5, 2.0,
                                         res),
                             np.linspace(0.5, 2.0,
                                         res),
                             np.linspace(2.5, 4.0,
                                         res))
                             
X_space = pd.DataFrame({'gapRatio':xx.ravel(),
                      'RI':yy.ravel(),
                      'Tm':uu.ravel(),
                      'zetaM':np.repeat(0.2,res**3)})

t0 = time.time()
downtime_plot = predict_DV(X_space,
                            mdl.gpc,
                            mdl_time_hit.kr,
                            mdl_time_miss.kr,
                            outcome=time_var)
tp = time.time() - t0
print("GPC-KR downtime prediction for %d inputs in %.3f s" % (X_space.shape[0],
                                                               tp))

# choice O_ridge bc SVR seems to hang, and KR overestimates (may need CV)
t0 = time.time()
space_drift = predict_DV(X_space,
                                      mdl.gpc,
                                      mdl_drift_hit.o_ridge,
                                      mdl_drift_miss.o_ridge,
                                      outcome='max_drift')
tp = time.time() - t0
print("GPC-OR drift prediction for %d inputs in %.3f s" % (X_space.shape[0],
                                                               tp))

# Transform predicted drift into probability

# drift -> collapse risk
from scipy.stats import lognorm
from math import log, exp

from scipy.stats import norm
inv_norm = norm.ppf(0.84)
beta_drift = 0.25
mean_log_drift = exp(log(0.1) - beta_drift*inv_norm) # 0.9945 is inverse normCDF of 0.84

ln_dist = lognorm(s=beta_drift, scale=mean_log_drift)

space_collapse_risk = pd.DataFrame(ln_dist.cdf(space_drift),
                                          columns=['collapse_risk_pred'])

#%%

plt.close('all')
plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
axis_font = 20
subt_font = 18
import matplotlib as mpl
label_size = 16
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 

# subset RI=2.0 in order to fit on 2d plot
downtime_plot_Ry = downtime_plot[X_space['RI'] == 2.0]
xx = np.array(X_space[X_space['RI'] == 2.0]['gapRatio']).reshape((50, 50))
yy = np.array(X_space[X_space['RI'] == 2.0]['Tm']).reshape((50, 50))
zz = np.array(downtime_plot_Ry)/50.0
Z = zz.reshape((50, 50))


fig, ax1 = plt.subplots(1, 1, figsize=(8, 6))

lvls = np.array([7., 14., 21., 28., 56.])
cs = ax1.contour(xx, yy, Z, linewidths=1.1, cmap='Blues', vmin=-50,
                 levels=lvls)
ax1.clabel(cs, fontsize=clabel_size)
ax1.legend()

steel_price = 2.00
coef_dict = get_steel_coefs(df, steel_per_unit=steel_price)

# <2 weeks for a team of 50
dts = [7*50, 14*50., 28*50.]
color_list = ['red', 'brown', 'black']
for j, dt_thresh in enumerate(dts):
    ok_time = X_space.loc[downtime_plot[time_var+'_pred']<=dt_thresh]
    
    X_design = X_space[X_space.index.isin(ok_time.index)]
        
    upfront_costs = calc_upfront_cost(X_design, coef_dict)
    cheapest_design_idx = upfront_costs.idxmin()
    design_upfront_cost = upfront_costs.min()
    # least upfront cost of the viable designs
    best_design = X_design.loc[cheapest_design_idx]
    design_downtime = space_downtime.iloc[cheapest_design_idx].item()
    design_repair_cost = space_repair_cost.iloc[cheapest_design_idx].item()
    design_collapse_risk = space_collapse_risk.iloc[cheapest_design_idx].item()
    design_PID = space_drift.iloc[cheapest_design_idx].item()
    
    theGap = best_design['gapRatio']
    theTm = best_design['Tm']
    
    ax1.vlines(x=theGap, ymin=2.5, ymax=theTm, color=color_list[j],
                linewidth=2.0)
    ax1.hlines(y=theTm, xmin=0.5, xmax=theGap, color=color_list[j],
                linewidth=2.0)
    ax1.text(theGap+0.02, 2.55, r'GR = '+f'{theGap:,.2f}'+r', $T_M=$'+f'{theTm:,.2f}', 
             rotation=90, fontsize=subt_font, color=color_list[j])
    ax1.plot([theGap], [theTm], marker='*', markersize=15, color=color_list[j])
    
    print(best_design)
    print(design_upfront_cost/1e6)
    
ax1.plot(0.5, 2.5, color='lightblue', label=r'Downtime (days)')
ax1.legend(fontsize=label_size, loc='best')

ax1.grid(visible=True)
ax1.set_title(r'$R_y \sim 2.0$, $\zeta_M = 0.20$', fontsize=title_font)
ax1.set_xlabel(r'Gap ratio (GR)', fontsize=axis_font)
ax1.set_ylabel(r'$T_M$', fontsize=axis_font)


#%% only 3 design (Tm, zeta)

res = 50

xx, yy, uu = np.meshgrid(np.linspace(0.5, 2.0,
                                         res),
                             np.linspace(2.5, 4.0,
                                         res),
                             np.linspace(0.1, 0.2,
                                         res))
                             
X_space = pd.DataFrame({'gapRatio':xx.ravel(),
                      'RI':np.repeat(2.0, res**3),
                      'Tm':yy.ravel(),
                      'zetaM':uu.ravel()})

t0 = time.time()
downtime_plot = predict_DV(X_space,
                            mdl.gpc,
                            mdl_time_hit.kr,
                            mdl_time_miss.kr,
                            outcome=time_var)
tp = time.time() - t0
print("GPC-KR downtime prediction for %d inputs in %.3f s" % (X_space.shape[0],
                                                               tp))

# choice O_ridge bc SVR seems to hang, and KR overestimates (may need CV)
t0 = time.time()
space_drift = predict_DV(X_space,
                                      mdl.gpc,
                                      mdl_drift_hit.o_ridge,
                                      mdl_drift_miss.o_ridge,
                                      outcome='max_drift')
tp = time.time() - t0
print("GPC-OR drift prediction for %d inputs in %.3f s" % (X_space.shape[0],
                                                               tp))

# Transform predicted drift into probability

# drift -> collapse risk
from scipy.stats import lognorm
from math import log, exp

from scipy.stats import norm
inv_norm = norm.ppf(0.84)
beta_drift = 0.25
mean_log_drift = exp(log(0.1) - beta_drift*inv_norm) # 0.9945 is inverse normCDF of 0.84

ln_dist = lognorm(s=beta_drift, scale=mean_log_drift)

space_collapse_risk = pd.DataFrame(ln_dist.cdf(space_drift),
                                          columns=['collapse_risk_pred'])

#%%
plt.close('all')
plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
axis_font = 20
subt_font = 18
import matplotlib as mpl
label_size = 16
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 

Tms = np.unique(yy)
zetas = np.unique(uu)
Tm_fix = [Tms[0], Tms[15], Tms[33], Tms[-1]]
zeta_fix = [zetas[0], zetas[25], zetas[-1]]
Tm_zeta_grid = np.zeros([4,3])

risk_thresh = 0.1
for i, Tm_cur in enumerate(Tm_fix):
    for j, zeta_cur in enumerate(zeta_fix):
        # subset RI=2.0 in order to fit on 2d plot
        subset_space = X_space[(X_space['Tm']==Tm_cur) &
                               (X_space['zetaM']==zeta_cur)]
        
        ok_risk = X_space.loc[space_collapse_risk['collapse_risk_pred']<=
                              risk_thresh]
        
        X_design = X_space[np.logical_and.reduce((
                X_space.index.isin(ok_risk.index),
                X_space.index.isin(subset_space.index)))]
        
        upfront_costs = calc_upfront_cost(X_design, coef_dict)
        cheapest_design_idx = upfront_costs.idxmin()
        design_upfront_cost = upfront_costs.min()
        # least upfront cost of the viable designs
        best_design = X_design.loc[cheapest_design_idx]
        Tm_zeta_grid[i][j] = best_design['gapRatio']
        
Tm_cols = [2.5, 3.0, 3.5, 4.0]
zeta_cols = [0.10, 0.15, 0.20]
Tm_zeta_df = pd.DataFrame(data=Tm_zeta_grid,
                          index=Tm_cols,
                          columns=zeta_cols).unstack(level=0).reset_index()
Tm_zeta_df.columns = ['zetaM', 'Tm', 'min_gap']

fig, ax1 = plt.subplots(1, 1, figsize=(8, 6))

sns.barplot(data=Tm_zeta_df, x="min_gap", y="Tm", hue="zetaM",
            orient='h', palette='Blues',
            ax=ax1)

legend_handles, _= ax1.get_legend_handles_labels()
ax1.legend(title=r'$\zeta_M$', fontsize=subt_font, loc='center right',
           title_fontsize=subt_font)

ax1.axvline(x=1.0, color='black', linestyle='--',
            linewidth=2.0)
ax1.text(0.95, 2.5, 'ASCE 7-22 minimum', 
         rotation=90, fontsize=subt_font, color='black')

ax1.set_xlim([0.6, 1.8])
ax1.grid(visible=True)
ax1.set_title(r'Targeting 10% collapse, $R_y=2.0$', fontsize=title_font)
ax1.set_xlabel(r'Recommended gap', fontsize=axis_font)
ax1.set_ylabel(r'$T_M$', fontsize=axis_font)
for container in ax1.containers:
    ax1.bar_label(container, fmt='%.2f', fontsize=14)
    
#%% full validation (IDA data)

val_dir = './data/tfp_mf_val/'
val_dir_loss = './results/tfp_mf_val/validation_full/'
val_file = 'addl_TFP_val.csv'

baseline_dir = './data/tfp_mf_val/'
baseline_dir_loss = './results/tfp_mf_val/baseline_full/'
baseline_file = 'addl_TFP_baseline.csv'

val_loss = pd.read_csv(val_dir_loss+'loss_estimate_data.csv', index_col=None)
base_loss = pd.read_csv(baseline_dir_loss+'loss_estimate_data.csv', index_col=None)

val_run = pd.read_csv(val_dir+val_file, index_col=None)
base_run = pd.read_csv(baseline_dir+baseline_file, index_col=None)
cost_var = 'cost_50%'
time_var = 'time_u_50%'


df_val = pd.concat([val_run, val_loss], axis=1)
df_val['max_drift'] = df_val[["driftMax1", "driftMax2", "driftMax3"]].max(axis=1)
df_val['collapse_probs'] = ln_dist.cdf(np.array(df_val['max_drift']))
df_val['repair_time'] = df[time_var]/50.0

df_base = pd.concat([base_run, base_loss], axis=1)
df_base['max_drift'] = df_base[["driftMax1", "driftMax2", "driftMax3"]].max(axis=1)
df_base['collapse_probs'] = ln_dist.cdf(np.array(df_base['max_drift']))
df_base['repair_time'] = df[time_var]/50.0

ida_levels = [1.0, 1.5, 2.0]
validation_collapse = np.zeros((3,))
baseline_collapse = np.zeros((3,))
validation_cost  = np.zeros((3,))
baseline_cost = np.zeros((3,))
validation_downtime = np.zeros((3,))
baseline_downtime = np.zeros((3,))

for i, lvl in enumerate(ida_levels):
    val_ida = val_loss[val_loss['IDA_level']==lvl]
    base_ida = base_loss[base_loss['IDA_level']==lvl]
    
    validation_collapse[i] = val_ida['collapse_freq'].mean()
    validation_downtime[i] = val_ida[time_var].mean()
    validation_cost[i] = val_ida[cost_var].mean()
    
    baseline_collapse[i] = base_ida['collapse_freq'].mean()
    baseline_downtime[i] = base_ida[time_var].mean()
    baseline_cost[i] = base_ida[cost_var].mean()
    
#%% fit validation curve (curve fit, not MLE)

from scipy.stats import lognorm
from scipy.optimize import curve_fit
f = lambda x,mu,sigma: lognorm(mu,sigma).cdf(x)

plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
axis_font = 18
subt_font = 18
label_size = 16
mpl.rcParams['xtick.labelsize'] = label_size 
mpl.rcParams['ytick.labelsize'] = label_size 
plt.close('all')

fig = plt.figure(figsize=(13, 6))


theta, beta = curve_fit(f,ida_levels,validation_collapse)[0]
xx = np.arange(0.01, 4.0, 0.01)
p = f(xx, theta, beta)

MCE_level = float(p[xx==1.0])
ax1=fig.add_subplot(1, 2, 1)
ax1.plot(xx, p)
ax1.axhline(0.025, linestyle='--', color='black')
ax1.axvline(1.0, linestyle='--', color='black')
ax1.text(2.0, 0.04, r'2.5% collapse risk',
         fontsize=subt_font, color='black')
ax1.text(0.1, MCE_level+0.01, f'{MCE_level:,.4f}',
         fontsize=subt_font, color='blue')
ax1.text(0.8, 0.7, r'$MCE_R$ level', rotation=90,
         fontsize=subt_font, color='black')

ax1.set_ylabel('Collapse probability', fontsize=axis_font)
ax1.set_xlabel(r'$MCE_R$ level', fontsize=axis_font)
ax1.set_title('Inverse design', fontsize=title_font)
for i, lvl in enumerate(ida_levels):
    ax1.plot([lvl], [validation_collapse[i]], 
             marker='x', markersize=15, color="red")
ax1.grid()
ax1.set_xlim([0, 4.0])
ax1.set_ylim([0, 1.0])

####
theta, beta = curve_fit(f,ida_levels,baseline_collapse)[0]
xx = np.arange(0.01, 4.0, 0.01)
p = f(xx, theta, beta)

MCE_level = float(p[xx==1.0])
ax2=fig.add_subplot(1, 2, 2)
ax2.plot(xx, p)
ax2.axhline(0.1, linestyle='--', color='black')
ax2.axvline(1.0, linestyle='--', color='black')
ax2.text(0.8, 0.7, r'$MCE_R$ level', rotation=90,
         fontsize=subt_font, color='black')
ax2.text(2.0, 0.12, r'10% collapse risk',
         fontsize=subt_font, color='black')
ax2.text(MCE_level, 0.12, f'{MCE_level:,.4f}',
         fontsize=subt_font, color='blue')

ax2.set_ylabel('Collapse probability', fontsize=axis_font)
ax2.set_xlabel(r'$MCE_R$ level', fontsize=axis_font)
ax2.set_title('Baseline design', fontsize=title_font)
for i, lvl in enumerate(ida_levels):
    ax2.plot([lvl], [baseline_collapse[i]], 
             marker='x', markersize=15, color="red")
ax2.grid()
ax2.set_xlim([0, 4.0])
ax2.set_ylim([0, 1.0])

fig.tight_layout()

#%%
plt.close('all')