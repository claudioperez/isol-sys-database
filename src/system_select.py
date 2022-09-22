############################################################################
#               System selection

# Created by:   Huy Pham
#               University of California, Berkeley

# Date created: August 2022

# Description:  

############################################################################


def random_system(num):
    
    import numpy as np

    # range of desired inputs
    system_dict   = {
        'structural_system' : [1, 4],
        'isolator_system' : [1, 2],
        'num_bays' : [3, 8]
    }

    # generate random integers within the bounds and place into array
    param_names = list(system_dict.keys())       
    num_categories = len(system_dict)
    system_selection = np.empty([num, num_categories])
    
    # set seed
    np.random.seed(985)
    
    for index, (key, bounds) in enumerate(system_dict.items()):
        system_selection[:,index] = np.random.randint(bounds[0], 
                                                      high=bounds[1]+1, 
                                                      size=num)

    return(param_names, system_selection)

def random_params(num):
    from scipy.stats import qmc
    import numpy as np

    # range of desired inputs
    # currently, this is approx'd to match MCER level (no site mod)
    inputDict   = {
        'S1'            : [0.8, 1.3],
        'Tm'            : [2.5, 4.0],
        'zetaM'         : [0.10, 0.20],
        'mu1'           : [0.01, 0.05],
        'R1'            : [15, 45],
        'moatAmpli'     : [0.3, 1.8],
        'Ry'            : [0.5, 2.0]
    }

    # create array of limits, then run LHS
    paramNames      = list(inputDict.keys())
    paramLimits     = np.asarray(list(inputDict.values()), dtype=np.float64).T
    
    lBounds = paramLimits[0,]
    uBounds = paramLimits[1,]
    
    dimVars = len(inputDict)
    sampler = qmc.LatinHypercube(d=dimVars, seed=985)
    sample = sampler.random(n=num)
    
    paramSet = qmc.scale(sample, lBounds, uBounds)

    return(paramNames, paramSet)

if __name__ == '__main__':

    system_names, systems       = random_system(50)
    param_names, params = random_params(50)
    print(systems.shape)