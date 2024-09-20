from myutils import *
import gurobipy as gb
from gurobipy import GRB
import sys
import math



def build_model(inst : Instance):
    xfix = inst.params['XFIX']
    if inst.params['POLICY'] != 'P0':
        return build_model_vrp(inst)
    mym = mymodel()
    mm = gb.Model('FSG')
    if inst.params['LOWER_BOUND']:
        #inst.p = 0
        #inst.delta ={k:0 for k in inst.delta}
        pass
    x = {(i,j) : mm.addVar(vtype = GRB.BINARY, name='x_{}_{}'.format(i,j)) for i in inst.Vp for j in inst.Vs if i != j }
    U = {(j,t) : mm.addVar(vtype = GRB.BINARY, name='U_{}_{}'.format(j,t)) for j in inst.Vs for t in inst.T}
    TBar = {i : mm.addVar(vtype = GRB.CONTINUOUS, lb = 0, name = 'TBar_{}'.format(i)) for i in inst.V}
    y = {(i,j,s) :mm.addVar(vtype = GRB.BINARY, name = 'y_{}_{}_{}'.format(i,j,s)) for i in inst.Vp for j in inst.Vs for s in inst.S if j!=i }
    Q = {(j,s) : mm.addVar(vtype=  GRB.CONTINUOUS, lb = 0, name = 'Q_{}_{}'.format(j,s)) for j in inst.V for s in inst.S}
    R = {(j,s) : mm.addVar(vtype=  GRB.CONTINUOUS, lb = 0, name = 'R_{}_{}'.format(j,s)) for j in range(inst.n+1, inst.n+inst.m+1) for s in inst.S}
    L = {(j,s) : mm.addVar(vtype=  GRB.CONTINUOUS, lb = 0, name = 'L_{}_{}'.format(j,s)) for j in range(1, inst.n + 1) for s in inst.S}
    rho = {(j,s) : mm.addVar(vtype=  GRB.BINARY,  name = 'rho_{}_{}'.format(j,s)) for j in range(1, inst.n + 1) for s in inst.S}
    lambd = {(j,s) : mm.addVar(vtype=  GRB.BINARY,  name = 'lambd_{}_{}'.format(j,s)) for j in range(1, inst.n + 1) for s in inst.S}
    alpha = {(j,s) : mm.addVar(vtype=  GRB.BINARY,  name = 'alpha_{}_{}'.format(j,s)) for j in range(1, inst.n + 1) for s in inst.S}

    mm.update()

    ZOB1 = gb.quicksum(inst.c[i,j] * x[i,j] for i in inst.Vp for j in inst.Vs if j != i) 
    ZOB2 = (1/inst.LS) * gb.quicksum(inst.c[i,j] * y[i,j,s] for s in inst.S for i in range(1, inst.n+1) for j in inst.Vs if j != i)
    ZOB3 = (1/inst.LS) * gb.quicksum(inst.c[j,0] * alpha[j,s] for s in inst.S for j in inst.V1)
    ZOB4 = (1/inst.LS) * gb.quicksum(inst.p * R[j,s] for s in inst.S for j in range(inst.n + 1, inst.n + inst.m + 1) )
    ZOB5 = (1/inst.LS) * gb.quicksum(inst.p * L[j,s] for s in inst.S for j in inst.V1)
    ZOB = ZOB1 - ZOB2 + ZOB3 + ZOB4 + ZOB5

    # if LOWER_BOUND:
    #    for i in inst.Vp:
    #     for j in inst.Vs:
    #         for s in inst.S:
    #             if j!=i:
    #                 y[i,j,s].ub = 0

    if len(xfix) > 0:
        for a in xfix:   # dictionary of x to be set equal to (i,j): value
            if xfix[a] < 0.9:
                x[a[0], a[1]].ub = 0
            else:
                x[a[0], a[1]].lb = 1
    if inst.params['FIX_SOLUTION']:  # used to calculate the EVV
        dfxres = pd.read_excel('results/' + inst.name + "_mean_res.xlsx", sheet_name='x')
        for index, row in dfxres.iterrows():
            if row['x'] < 0.99:
                x[row['i'], row['j']].ub = 0
            else:
                x[row['i'], row['j']].lb = 1
    if inst.params['INIT_SOL']:
        dfxres = pd.read_excel('results/' + inst.name + "_res.xlsx", sheet_name='x')
        for index, row in dfxres.iterrows():
            if row['x'] < 0.99:
                x[row['i'], row['j']].Start = 0
            else:
                x[row['i'], row['j']].Start = 1
    

    mm.setObjective(ZOB, GRB.MINIMIZE)
    mm.update()

    mm.addConstrs((gb.quicksum(x[i,j] for j in inst.Vs if j!=i) - gb.quicksum(U[i,t] for t in inst.T) == 0 for i in inst.V1  ), name='ct02.1')
    mm.addConstrs((gb.quicksum(x[j,i] for j in inst.Vp if j!=i) - gb.quicksum(U[i,t] for t in inst.T) == 0 for i in inst.V1  ), name='ct02.2')
    mm.addConstr( gb.quicksum(x[0,j] for j in inst.Vs)  == inst.m , name = 'ct03' )
    mm.addConstrs( (gb.quicksum(x[j,i] for j in inst.Vp) == 1 for i in range (inst.n+1, inst.n + inst.m + 1) ), name='ct04'  )

    mm.addConstrs((gb.quicksum(U[j,t] for t in inst.T) == 1 for j in inst.Vs), name = 'ct05')
    mm.addConstr(TBar[0] == 0, name='ct06')
    mm.addConstrs(( TBar[j] - TBar[i] - inst.t[i,j] + inst.Tmax * (1 - x[i,j]) >=0 for i in inst.Vp for j in inst.Vs if j != i ), name='ct07' )
    mm.addConstrs(( inst.etw[t] - inst.Tmax * (1 - U[j,t]) - TBar[j]  <= 0 for j in inst.Vs for t in inst.T), name = 'ct08.1')
    mm.addConstrs(( TBar[j]  - inst.ltw[t] - inst.Tmax * (1 - U[j,t]) <= 0 for j in inst.Vs for t in inst.T), name = 'ct08.2')

    mm.addConstrs((Q[0,s] == 0  for s in inst.S), name = 'ct09')
    mm.addConstrs((Q[j,s] - Q[i,s] + inst.M * (1 - x[i,j]) - inst.d[j] - gb.quicksum( inst.delta[j,tau,s] * U[j,t] for t in inst.T for tau in range(1, t+1 ))  >= 0
                   for s in inst.S for i in inst.Vp for j in range(1, inst.n + 1) if j != i), name = 'ct10')
    mm.addConstrs((Q[j,s] - Q[i,s] - inst.M * (1 - x[i,j]) - inst.d[j] - gb.quicksum( inst.delta[j,tau,s] * U[j,t] for t in inst.T for tau in range(1, t+1 ))  <= 0
                   for s in inst.S for i in inst.Vp for j in range(1, inst.n + 1) if j != i), name = 'ct10_new')
    mm.addConstrs((Q[j,s] - Q[i,s] + inst.M * (1 - x[i,j]) >= 0 for s in inst.S for i in inst.Vp for j in range(inst.n + 1, inst.n + inst.m + 1)), name = 'ct11')
    mm.addConstrs((Q[j,s] - Q[i,s] - inst.M * (1 - x[i,j]) <= 0 for s in inst.S for i in inst.Vp for j in range(inst.n + 1, inst.n + inst.m + 1)), name = 'ct11_new')
    mm.addConstrs((R[j,s] - Q[j,s] + inst.C >= 0 for s in inst.S for j in range(inst.n + 1, inst.n + inst.m + 1)), name = 'ct12') 
    #mm.addConstrs((R[j,s]  >= 0 for s in inst.S for j in range(inst.n + 1, inst.n + inst.m + 1)), name = 'ct13') already considered in variable definition
    
    mm.addConstrs((L[j,s] - gb.quicksum( inst.delta[j,tau,s] * U[j,t] for t in inst.T for tau in range(t+1, inst.LT + 1)) == 0 for s in inst.S for j in inst.V1), name = 'ct14')

    mm.addConstrs((rho[j,s] - ((1/inst.Qmax)*(Q[j,s] - inst.C)) >= 0 for s in inst.S for j in inst.V1), name = 'ct15')
    mm.addConstrs((rho[j,s] + ((1/inst.Qmax)*(inst.C - Q[j,s] )) <= 1 for s in inst.S for j in inst.V1), name = 'ct16') 

    #mm.addConstrs((rho[j,s] + inst.Qmax*R[j,s] >= 1 for s in inst.S for j in range(1, inst.n + 1)) , name = 'ct_rho_new')

    mm.addConstrs((y[i,j,s] - 0.5 * (x[i,j] + rho[i,s]) <= 0 for s in inst.S for i in inst.V1 for j in inst.Vs if j != i), name = 'ct17')

    mm.addConstrs( (y[0,j,s] == 0 for s in inst.S for j in inst.Vs), name='cty0')
    mm.addConstrs(( alpha[j,s] == gb.quicksum(y[j,i,s] for i in inst.Vs if j!=i) - gb.quicksum(y[i,j,s] for i in range(1, inst.n+1) if j!=i)  for s in inst.S for j in range(1, inst.n + 1)), name = 'ctyalpha')

    if inst.params['VALID_INEQUALITIES']:
        mm.addConstr(  gb.quicksum(x[i,j] for i in inst.Vp for j in inst.Vs  if i != j  ) <= len(inst.V1) + inst.m, name="vi1.1" )
        mm.addConstr(  gb.quicksum(x[i,j] for i in inst.Vp for j in inst.Vs  if i != j ) >= len(inst.V1) , name="vi1.2" )
        mm.addConstrs( ( gb.quicksum( y[i,j,s] for i in inst.Vp for j in inst.Vs if j!=i ) -  gb.quicksum(rho[j,s] for j in range(1, inst.n + 1)  ) <= 0 for s in inst.S), name="vi2" )
    
    """
    mm.addConstr(x[0,1]==1)
    mm.addConstr(x[1,2]==1)
    mm.addConstr(x[2,3]==1)
    mm.addConstr(x[3,4]==1)
    mm.addConstr(x[4,5]==1)
    mm.addConstr(x[5,11]==1)
    mm.addConstr(x[0,10]==1)
    mm.addConstr(x[10,9]==1)
    mm.addConstr(x[9,8]==1)
    mm.addConstr(x[8,7]==1)
    mm.addConstr(x[7,6]==1)
    mm.addConstr(x[6,12]==1)
    """
    
    mm.update()
    if (inst.params['WRITE_LP']):
        mm.write('results/model_'+inst.name+'.lp')

    mym.set(mm, x, U, TBar, y, Q, R, L, rho, lambd, alpha, ZOB1, ZOB2, ZOB3, ZOB4, ZOB5, 'STOCHASTIC')
    return mym

def build_model_vrp(inst : Instance):
    mym = mymodel()
    mm = gb.Model('FSG')
    policy = inst.params['POLICY']
    capResize = 0.2

    d = {k:v for k,v in inst.d.items()}
    C = inst.C

    if policy == 'P1':
        pass
    if policy == 'P2' or policy == 'P4' or policy == 'P5' or policy == 'P6' or policy == 'P7':
        for j in range(1, inst.n + 1):
            mean = 0
            for s in inst.S:  
                for t in inst.T:
                    mean += inst.delta[j,t,s]
            mean = mean/inst.LS
            d[j] = d[j] + mean

    if policy == 'P3':
        NT = math.ceil(inst.LT/2)
        for j in range(1, inst.n + 1):
            mean = 0
            for s in inst.S:  
                for t in range(1, NT+1):
                    mean += inst.delta[j,t,s]
            mean = mean/(inst.LS*NT)
            d[j] = d[j] + mean
        
    if policy == 'P4':
        C = C*(1-capResize)
    if policy == 'P5':
        pass
    if policy == 'P6':
        pass
    if policy == 'P7':
        C = C*(0.9)

    
    
    if inst.params['LOWER_BOUND']:
        #inst.p = 0
        #inst.delta ={k:0 for k in inst.delta}
        pass

    x = {(i,j) : mm.addVar(vtype = GRB.BINARY, name='x_{}_{}'.format(i,j)) for i in inst.Vp for j in inst.Vs if i != j }
    

    U = {(j,t) : mm.addVar(vtype = GRB.BINARY, name='U_{}_{}'.format(j,t)) for j in inst.Vs for t in inst.T}
    TBar = {i : mm.addVar(vtype = GRB.CONTINUOUS, lb = 0, name = 'TBar_{}'.format(i)) for i in inst.V}
    Q = {j : mm.addVar(vtype=  GRB.CONTINUOUS, lb = 0, name = 'Q_{}'.format(j)) for j in inst.V}
    mu = {j : mm.addVar(vtype = GRB.CONTINUOUS, lb=0, name='mu_{}'.format(j)) for j in inst.V}
    u = {}
    if policy == 'P6':
        u = {j : mm.addVar(vtype=GRB.INTEGER, lb=0, name = 'u_{}'.format(j)) for j in inst.V }


    mm.update()

    K = 1000000
    ZOB = None

    if policy == 'P6':
        ZOB = gb.quicksum((1/inst.t[0,j])*u[j] for j in inst.V1 )
    else:
        ZOB1 = gb.quicksum(inst.c[i,j] * x[i,j] for i in inst.Vp for j in inst.Vs if j != i) 
        ZOB2 = K * gb.quicksum(mu[j] for j in inst.V)
        ZOB = ZOB1 + ZOB2 

    # if LOWER_BOUND:
    #    for i in inst.Vp:
    #     for j in inst.Vs:
    #         for s in inst.S:
    #             if j!=i:
    #                 y[i,j,s].ub = 0


    mm.setObjective(ZOB, GRB.MINIMIZE)
    mm.update()

    mm.addConstrs((gb.quicksum(x[i,j] for j in inst.Vs if j!=i) - gb.quicksum(U[i,t] for t in inst.T) == 0 for i in inst.V1  ), name='ct02.1')
    mm.addConstrs((gb.quicksum(x[j,i] for j in inst.Vp if j!=i) - gb.quicksum(U[i,t] for t in inst.T) == 0 for i in inst.V1  ), name='ct02.2')
    mm.addConstr( gb.quicksum(x[0,j] for j in inst.Vs)  == inst.m , name = 'ct03' )
    mm.addConstrs( (gb.quicksum(x[j,i] for j in inst.Vp) == 1 for i in range (inst.n+1, inst.n + inst.m + 1) ), name='ct04'  )

    mm.addConstrs((gb.quicksum(U[j,t] for t in inst.T) == 1 for j in inst.Vs), name = 'ct05')
    mm.addConstr(TBar[0] == 0, name='ct06')
    mm.addConstrs(( TBar[j] - TBar[i] - inst.t[i,j] + inst.Tmax * (1 - x[i,j]) >=0 for i in inst.Vp for j in inst.Vs if j != i ), name='ct07' )
    mm.addConstrs(( inst.etw[t] - inst.Tmax * (1 - U[j,t]) - TBar[j]  <= 0 for j in inst.Vs for t in inst.T), name = 'ct08.1')
    mm.addConstrs(( TBar[j]  - inst.ltw[t] - inst.Tmax * (1 - U[j,t]) <= 0 for j in inst.Vs for t in inst.T), name = 'ct08.2')

    mm.addConstrs((Q[0] == 0  for s in inst.S), name = 'ct09')
    mm.addConstrs((Q[j] - Q[i] + inst.M * (1 - x[i,j]) - d[j]   >= 0   for i in inst.Vp for j in range(1, inst.n + 1) if j != i), name = 'ct10')
    #mm.addConstrs((Q[j] - Q[i] - inst.M * (1 - x[i,j]) - inst.d[j] for t in inst.T for tau in range(1, t+1 )  <= 0   for i in inst.Vp for j in range(1, inst.n + 1) if j != i), name = 'ct10_new')
    mm.addConstrs((Q[j] - Q[i] + inst.M * (1 - x[i,j]) >= 0 for i in inst.Vp for j in range(inst.n + 1, inst.n + inst.m + 1)), name = 'ct11')
    #mm.addConstrs((Q[j] - Q[i] - inst.M * (1 - x[i,j]) <= 0 for i in inst.Vp for j in range(inst.n + 1, inst.n + inst.m + 1)), name = 'ct11_new')
    
    if policy == 'P5':
        f = {j : capResize if j%2 == 0 else -capResize for j in inst.V}
        mm.addConstrs((Q[j] <= C*(1 + f[j]) + mu[j] for j in inst.V), name = 'ctcap')
    else:
        mm.addConstrs((Q[j] <= C + mu[j] for j in inst.V), name = 'ctcap')
    
    if policy == 'P6':
        mm.addConstrs((u[j] - u[i] - 1 + (len(inst.Vp) - 1)*(1 - x[i,j]) >=0  for j in inst.Vs for i in inst.Vp if i != j), name = 'ctu')


    if inst.params['VALID_INEQUALITIES']:
        pass
 
    """
    mm.addConstr(x[0,1]==1)
    mm.addConstr(x[1,2]==1)
    mm.addConstr(x[2,3]==1)
    mm.addConstr(x[3,4]==1)
    mm.addConstr(x[4,5]==1)
    mm.addConstr(x[5,11]==1)
    mm.addConstr(x[0,10]==1)
    mm.addConstr(x[10,9]==1)
    mm.addConstr(x[9,8]==1)
    mm.addConstr(x[8,7]==1)
    mm.addConstr(x[7,6]==1)
    mm.addConstr(x[6,12]==1)
    """
    
    mm.update()
    if (inst.params['WRITE_LP']):
        mm.write('results/model_'+inst.name+'_'+ policy +'.lp')
    if policy != 'P6':
        mym.set(mm, x, U, TBar, None, Q, None, None, None, None, None, ZOB1, ZOB2, 0, 0, 0, 'POLICY')
    else:
            mym.set(mm, x, U, TBar, None, Q, None, None, None, None, None, ZOB, 0, 0, 0, 0, 'POLICY')
    return mym

def run_model(inst : Instance, mym : mymodel):
    mm = mym.m
    mm.Params.TimeLimit = inst.params['max_runtime']
    #mm.Params.IntFeasTol = 1e-7
    mm.optimize()
    print('Optimization ended with status (2=optimal, 3=infeasible, 5=inf_or_unbounded, 9=timlimit, 11=interrupted)', mm.Status)

def run(params : dict):
    inst = load_instance(pms)
    print ("loaded instance with ", inst.n, ' nodes' )
    print (inst.to_string())

    print("building model")
    mym = build_model(inst)

    print("run model")
    run_model(inst, mym)

    print("save solution to excel (if a solution has been found)")
    if mym.m.Status in [2,9,11]:
        print('object value: ', mym.m.ObjVal)
        print(mym.Z1.getValue())
        print(mym.Z2.getValue())
        print(mym.Z3.getValue())
        print(mym.Z4.getValue())
        print(mym.Z5.getValue())
        fsolname = 'results/out_'+inst.name
        fsolname += '_fix.sol' if inst.params['FIX_SOLUTION']==True  else '.sol'
        mym.m.write(fsolname)
        mym.to_excel(inst)
    return mym


if __name__ == "__main__":

    #inst_names = ['I2_N7_T100_C140_0', 'I2_N7_T100_C210_0', 'I2_N7_T100_C280_0']
    #inst_names = ['I2_N10_T30_C250_0', 'I2_N10_T30_C275_0', 'I2_N10_T30_C325_0','I2_N10_T100_C275_0', 'I2_N10_T100_C325_0' ]
    inst_names = ['I2_N7_T30_C280_0', 'I2_N7_T30_C210_0', 'I2_N7_T30_C140_0', 'I2_N7_T100_C280_0', 'I2_N7_T100_C210_0', 'I2_N7_T100_C140_0', 
                   'I2_N5_T30_C200_0', 'I2_N5_T30_C150_0', 'I2_N5_T30_C100_0', 'I2_N5_T100_C200_0', 'I2_N5_T100_C150_0', 'I2_N5_T100_C100_0', 
                   'I2_N10_T30_C400_0', 'I2_N10_T30_C350_0', 'I2_N10_T30_C325_0', 'I2_N10_T30_C300_0', 'I2_N10_T30_C275_0', 'I2_N10_T100_C400_0', 
                   'I2_N10_T100_C350_0', 'I2_N10_T100_C325_0', 'I2_N10_T100_C300_0', 'I2_N10_T100_C275_0']
    for inst_name in inst_names:  #'I2_S1_0_C100'
        if len(sys.argv) > 1:
            inst_name = sys.argv[1]
        fp = open('params.json')
        pms = json.load(fp)

        if pms['MODEL_TYPE'] == "POLICY":
            policies = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7']
            policies = ['P7']
            pms['inst_name'] = inst_name
            pms['FIX_SOLUTION'] = False
            inst = load_instance(pms)
            print ("loaded instance with ", inst.n, ' nodes' )
            print (inst.to_string())

            
            for p in policies:

                ###
                # Run POLICY
                ###    
                
                print("###### Processing Instance named: ", inst_name, '   #############')
                print("######  POLICY:             ", p, '#################')
                print("building model")
                pms['POLICY'] = p
                mym = build_model(inst)

                print(f"run model with policy {p}")
                run_model(inst, mym)
                # take the x solution
                xfix = {(k[0],k[1]): v.x for k,v in mym.x.items()}
                # set the stochastic model with fix x
                pms['POLICY'] = 'P0'
                pms['XFIX'] = xfix
                # build the stochastic model with P0 and x fix
                print("INNEST X SOLUTION OF " + p + " POLICY INTO STOCHASTIC MODEL AND SOLVE IT")
                mym = build_model(inst)
                print(f"run model with policy {p}")
                run_model(inst, mym)

                print("save solution to excel (if a solution has been found)")
                if mym.m.Status in [2,9,11]:
                    print('object value: ', mym.m.ObjVal)
                    print(mym.Z1.getValue())
                    print(mym.Z2.getValue())
                    print(mym.Z3.getValue())
                    print(mym.Z4.getValue())
                    print(mym.Z5.getValue())
                    fsolname = 'results/out_'+inst.name
                    fsolname += '_fix.sol' if inst.params['FIX_SOLUTION']==True  else '.sol'
                    mym.m.write(fsolname)
                    # reset the current policy in order to write it to disk as filename
                    pms['POLICY'] = p
                    mym.to_excel(inst)

                    # reset x solution in order to pass to the next policy
                pms['XFIX'] = {}
        
        else:
            ###
            # Run stochastic model
            ###    

            pms['inst_name'] = inst_name
            pms['FIX_SOLUTION'] = False
            print("###### Processing Instance named: ", inst_name, '   #############')
            print("######  FIX SOLUTION:             ", pms['FIX_SOLUTION'], '#################')
            run(pms)


            ###
            # Run average model
            ### 
            inst_name_mean = inst_name + '_mean'
            pms['inst_name'] = inst_name_mean
            pms['FIX_SOLUTION'] = False
            print("###### Processing Instance named: ", inst_name, '   #############')
            print("######  FIX SOLUTION:             ", pms['FIX_SOLUTION'], '#################')
            run(pms)


            ########
            # Run FIXED MODEL  (EEV)
            ########
            pms['inst_name'] = inst_name
            pms['FIX_SOLUTION'] = True
            print("###### Processing Instance named: ", inst_name, '   #############')
            print("######  FIX SOLUTION:             ", pms['FIX_SOLUTION'], '#################')
            run(pms)


