from __future__ import print_function, division
from warnings import warn

import pandas as pd
import numpy as np

from nilmtk.disaggregate import Disaggregator
from hmmlearn import hmm
from collections import OrderedDict

import cvxpy as cvx
from collections import Counter
import matplotlib.pyplot as plt
import time
class AFHMM(Disaggregator):
    """1 dimensional baseline Mean algorithm.

    Attributes
    ----------
    model : list of dicts
       Each dict has these keys:
           mean : list of mean values, one for each appliance (the mean power
           (Watts)) training_metadata : The appliance type (and perhaps some
           other metadata) for each model.

    MIN_CHUNK_LENGTH : int

    MODEL_NAME = string
    """

    def __init__(self, d):
        self.model = []
        self.MIN_CHUNK_LENGTH = 100
        self.MODEL_NAME = 'AFHMM'
        self.default_num_states = 2

    def partial_fit(self, train_main, train_appliances, **load_kwargs):
        '''
            train_main :- pd.DataFrame It will contain the mains reading.
            train_appliances :- list of tuples [('appliance1',df1),('appliance2',df2),...]

        '''
        train_main = pd.concat(train_main, axis=0)
        train_app_tmp = []

        for app_name, df_list in train_appliances:
            df_list = pd.concat(df_list, axis=0)
            train_app_tmp.append((app_name,df_list))

        train_appliances = train_app_tmp


        learnt_model = OrderedDict()

        means_vector = []

        one_hot_states_vector = []

        pi_s_vector = []

        transmat_vector = []

        states_vector = []

        train_main = train_main.values.flatten().reshape((-1,1))

        for appliance_name, power in train_appliances:
            #print (appliance_name)
            
            X = power.values.reshape((-1,1))

            learnt_model[appliance_name] = hmm.GaussianHMM(self.default_num_states, "full")
            # Fit
            learnt_model[appliance_name].fit(X)

            means = learnt_model[appliance_name].means_.flatten().reshape((-1,1))
            states = learnt_model[appliance_name].predict(X)
            transmat = learnt_model[appliance_name].transmat_
            pi = learnt_model[appliance_name].startprob_.flatten()
            print (Counter(states.flatten()))
            nb_classes = self.default_num_states
            targets = states.reshape(-1)
            
            means_vector.append(means)
            pi_s_vector.append(pi)
            transmat_vector.append(transmat.T)
            states_vector.append(states)

        #print (np.sum(transmat_vector[0],axis=1))
        #print (np.sum(transmat_vector[0],axis=0))
            #print (states.shape)
            #print (one_hot_targets.shape)

        # one_hot_states_vector = np.array(one_hot_states_vector)

        # # print (transmat_vector[0])
        # # print (np.sum(transmat_vector[0],axis=0))
        # # print (np.sum(transmat_vector[0],axis=1))
        # appliance_variable_matrix = []

        # #print (len(states_vector))
        # #variable_matrix = np.zeros((len(appliance_states),self.default_num_states,self.default_num_states))

        # for appliance_states in states_vector:

        #    variable_matrix = np.zeros((len(appliance_states),self.default_num_states,self.default_num_states))

        #    for i in range(1,len(appliance_states)):
        #        current_state =  appliance_states[i]
        #        previous_state = appliance_states[i-1]
        #        variable_matrix[i,current_state, previous_state] = 1
        #    appliance_variable_matrix.append(variable_matrix)

        # appliance_variable_matrix = np.array(appliance_variable_matrix)
        # term_1_list = []

        # term_2_list = []

        expression = 0

        sigma = np.ones((len(train_main)))   # The initial vector of Sigmas      

        for epoch in range(10):

            if epoch%2==1:
                # The alernative Minimization

                usage = np.zeros((len(train_main)))

                for appliance_id in range(len(train_appliances)):

                    usage+= np.sum(s_[appliance_id]@means_vector[appliance_id],axis=1)

                plt.figure(figsize=(20,8))
                plt.plot(np.where(usage.flatten()>0,usage.flatten(),0),label='pred')
                plt.plot(train_appliances[appliance_id][1].values,label='truth')
                plt.plot(train_main.flatten(),label='Input')
                plt.legend()
                plt.show()

                sigma = train_main.flatten() - usage.flatten()
                sigma = np.where(sigma>1,sigma,1)
               

            if epoch%2==0:
            
                constraints = []

                cvx_state_vectors = []

                cvx_variable_matrices = []

                delta = cvx.Variable(shape=(len(train_main),), name='delta_t')

                for appliance_id in range(len(train_appliances)):

        
                    state_vector = cvx.Variable(shape=(len(train_main), self.default_num_states), name='state_vec-%s'%(appliance_id))
                    #print ("oollala")
                    #print (state_vector.shape)
                    
                    cvx_state_vectors.append(state_vector)

                    # Enforcing that their values are ranged
                    constraints+=[cvx_state_vectors[appliance_id]>=0]
                    constraints+=[cvx_state_vectors[appliance_id]<=1]

                    # Enforcing that sum of states equals 1
                    for t in range(len(train_main)): # 6c
                        constraints+=[cvx.sum(cvx_state_vectors[appliance_id][t])==1]

                    # Creating Variable matrices for every appliance
                    
                    appliance_variable_matrix = []
                    for t in range(len(train_main)):

                        matrix = cvx.Variable(shape=(self.default_num_states, self.default_num_states), name='variable_matrix-%s-%d'%(appliance_id,t))
                        appliance_variable_matrix.append(matrix)
                    
                    cvx_variable_matrices.append(appliance_variable_matrix)

                    # Enforcing that their values are ranged
                    for t in range(len(train_main)):                
                        constraints+=[cvx_variable_matrices[appliance_id][t]>=0]
                        constraints+=[cvx_variable_matrices[appliance_id][t]<=1]

                        
                    # Constraint 6e
                    for t in range(0,len(train_main)): # 6e
                        for i in range(self.default_num_states):
                            constraints+=[cvx.sum(cvx_variable_matrices[appliance_id][t][i]) == cvx_state_vectors[appliance_id][t][i]]
                    # Constraint 6d
                    for t in range(1,len(train_main)): # 6d
                        for i in range(self.default_num_states):
                            constraints+=[cvx.sum((cvx_variable_matrices[appliance_id][t]).T[i]) == cvx_state_vectors[appliance_id][t-1][i]]
                # Second order cone constraints
                soc_constraints = []

                for t in range(len(train_main)):

                    total_observed_reading = 0#np.zeros((1,1))
                    
                    #print (len(cvx_state_vectors))
                    for appliance_id in range(len(train_appliances)):
                        for j in range(self.default_num_states):
                            #print (cvx_state_vectors[appliance_id].shape)
                            #print (cvx_state_vectors[appliance_id][t][j])
                            #print (means_vector[appliance_id][j])
                            
                            total_observed_reading+=cvx.sum(cvx.multiply(cvx_state_vectors[appliance_id][t][j],means_vector[appliance_id][j]))
                            #soc_constraints+=[cvx.SOC( delta[t], train_main[t] - total_observed_reading)]
                    #soc_constraints+=[ cvx.norm(train_main[t] - total_observed_reading)**2 <=  delta[t]]
                    soc_constraints+=[cvx.SOC( delta[t], train_main[t] - total_observed_reading)]


                # total_observed_reading = np.zeros((train_main.shape))

                # for appliance_id in range(len(train_appliances)):
                #     print(appliance_id)
                #     print (len(cvx_state_vectors))
                #     #print
                #     total_observed_reading+=cvx_state_vectors[appliance_id]@means_vector[appliance_id]

                # for t in range(len(train_main)):
                #     #soc_constraints+=[cvx.SOC( delta[t], train_main[t] - total_observed_reading[t])]
                #     soc_constraints+=[ cvx.norm(train_main[t] - total_observed_reading[t])**2 <=  delta[t]]


                # print ("After SOC")
                # print (train_main[t].shape)
                # print (total_observed_reading[t].shape)
                # print (delta[t].shape)
                #print (cvx.sum(cvx.multiply(cvx_state_vectors[appliance_id][t][j],means_vector[appliance_id][j])).shape)
                    #print ('After SOC')
                    #print (train_main[t].shape,total_observed_reading.shape, delta )
                # observed_usage = np.zeros((len(train_main),1))

                # for t in range(len(train_main)):
                #     #observed_usage[t]    
                #     for appliance_id in range(len(train_appliances)):
                #     observed_usage+=cvx_state_vectors[appliance_id] @ means_vector[appliance_id]
                # for t in range(len(train_main)):                           
                #     soc_constraints+=[cvx.SOC(delta[t], train_main[t] - observed_usage)]
                    
                constraints+=soc_constraints
                # intializing the Expression
                
                expression = 0
                
                for appliance_id,( appliance_name, appliance_power) in enumerate(train_appliances):
                
                    # First loop is over appliances

                    variable_matrix = cvx_variable_matrices[appliance_id]
                    
                    transmat = transmat_vector[appliance_id]
                    # Next loop is over different time-stamps
                    
                    for matrix in variable_matrix:
                        expression-=cvx.sum(cvx.multiply(matrix,np.log(transmat)))
                    
                    one_hot_states = cvx_state_vectors[appliance_id]
                    pi = pi_s_vector[appliance_id]

                    # The expression involving start states
                    first_one_hot_states = one_hot_states[0]
                    #print ("Pis")
                    #print (first_one_hot_states.shape)
                    #print (pi.shape)
                    expression-= cvx.sum(cvx.multiply(first_one_hot_states,np.log(pi)))
                        
                #print (delta.shape)
                #print (sigma.shape)
                
                for t in range(len(train_main)):
                    #print (delta[i].shape)
                    #print (sigma[i].shape)
                    expression+=.5 * (delta[t] / (sigma[t]**2))

                expression = cvx.Minimize(expression)

                u = time.time()
                #print (sigma.shape)
                prob = cvx.Problem(expression, constraints)
                #prob.solve(solver=cvx.ECOS_BB)
                prob.solve(cvx.SCS, verbose=True)
                print (prob.value)
                print (time.time()-u)
                s_ = [i.value for i in cvx_state_vectors]
                print (delta.value)
                print (s_[0])
                print (np.sum(s_[0],axis=1))
                print ("Over Iteration")

        #    #print (one_hot_states.shape)
        #    #print (means_vector[appliance_id].shape)
        #    #print (term_3.shape)
        #    #print ((np.sum(one_hot_states*means_vector[appliance_id],axis=1).shape))
        #    term_3+= np.sum(one_hot_states*means_vector[appliance_id],axis=1)

            
        #    #print (term_3.shape)
        #    # term_1_list.append(variable_matrix*np.log(transmat))
        #    # term_2_list.append(one_hot_states*np.log(pi))
        #    #term_3+=hone#appliance_power.values.reshape((-1,1))

        # #print (np.array(term_1_list).shape,np.array(term_2_list).shape,term_3.shape)
        # # term_1_list = np.array(term_1_list)
        # # term_2_list = np.array(term_2_list)



        # # sigma = 30

        # # expression = 0
        # # s = 0
        # # for appliance_id in range(len(term_1_list)):

        # #  for t in range(len(term_1_list[appliance_id])):

        # #      matrix =  term_1_list[appliance_id, t]
        # #      s-=np.sum(matrix)
        # #      #print (matrix.shape)
        # #      #print (matrix)
        # #      expression-=cvx.sum(matrix)



        # # for appliance_id in range(len(term_2_list)):
        # #  matrix = term_2_list[appliance_id]
        # #  s-=np.sum(matrix)
        # #  #print (matrix)
        # #  expression-=cvx.sum(matrix)

        # #print (train_main.shape)
        # #print (expression.value)
        # sigma = 30
        # expression+= .5 * (cvx.norm(train_main - term_3) **2)/(sigma**2)

        # constraints = [one_hot_states_vector<=1, one_hot_states_vector>=0, appliance_variable_matrix>=0,appliance_variable_matrix<=1]

        # exp = '['
        # for appliance_id in range(len(one_hot_states_vector)):

        #    states_vector = one_hot_states_vector[appliance_id]

        #    for t in range(len(states_vector)):
        #        exp+='cvx.sum(one_hot_states_vector[%s,%s])==1'%(appliance_id,t)
        #        exp+=','
        # exp = exp[:-1]
        # exp+=']'
        
        # constraints+=eval(exp)

        # print (expression.value)

        # expression = cvx.Minimize(expression)

        # prob = cvx.Problem(expression, constraints)

        # H = cvx.Variable(shape=(10, 20,30), name='H')
        # print (prob.value) 
        # #print (eval(exp))

        # #print (expression.value)

        # # plt.figure(figsize=(20,8))
        # # plt.plot(train_main.flatten())
        # # plt.plot(term_3.flatten())
        # # plt.show()
        # #expresssion = -cvx.sum(term_1_list) - cvx.sum(term_2_list) + 

        # # print (expression.value)
        # # print (s)

        # # constraints = []

        # # s = "["
        # # for appliance_id in range(len(states_vector)):

        # #  for t in range(len(appliance_id)):
        # #      s+=



        # # term_1 = variable_matrix*(transmat.T)
        # # print (one_hot_states.shape)
        # # term_2 = one_hot_states[0]*pi

        # # #term_3 =  train_main - X
        # # print (term_2.shape, term_1.shape,term_3.shape)
        # # print (train_main.shape)
        #    #print (variable_matrix[1])
        #    #print (variable_matrix[-1])
        #    #print (appliance_states)


        # #print (learnt_model[appliance_name].transmat_)
        # # print (means_vector[0])
        # # print (means_vector[1])
        # # print (states)
        # # print (one_hot_targets)
        # # means_vector = []

        # # for appliance_name in learnt_model:

        # #  for mean_val in learnt_model[appliance_name].predict(X):
        # #      means_vector.append(mean_val)
