'''
    SAC case1 (d-based rgcn p-based rgcn)
'''

import torch
import numpy as np
import os
import time
import json
from tabulate import tabulate
import gymnasium as gym
from gymnasium import spaces

import pickle

from ckt_graphs import GraphOTA
from dev_params import DeviceParams
from utils import ActionNormalizer, OutputParser_ota
from sac import SACAgent
from models import ActorCriticRGCN, ActorCriticGCN, ActorCriticGAT, ActorCriticMLP

from ota import OTAEnv

from datetime import datetime

date = datetime.today().strftime('%Y-%m-%d')

PWD = os.getcwd()
SPICE_NETLIST_DIR = f'{PWD}/simulations'
os.environ['CUDA_LAUNCH_BLOCKING'] = "1"

CktGraph = GraphOTA
GNN = ActorCriticRGCN  # you can select other GNN
rew_eng = CktGraph().rew_eng

""" Regsiter the environemnt to gymnasium """

from gymnasium.envs.registration import register

env_id = 'sky130ota-v0'

env_dict = gym.envs.registration.registry.copy()

for env in env_dict:
    if env_id in env:
        print("Remove {} from registry".format(env))
        del gym.envs.registration.registry[env]

print("Register the environment")
register(
    id=env_id,
    entry_point='ota:OTAEnv',
    max_episode_steps=50,
)
env = gym.make(env_id)

""" Run intial op experiment """
run_intial = False
if run_intial == True:
    env = OTAEnv()
    env._init_random_sim(100)

start_time = time.perf_counter()

""" Do the training """
# parameters
num_steps = 5000
# num_steps = 10000
memory_size = 100000
batch_size = 128
initial_random_steps = 1000
# batch_size = 1
# initial_random_steps = 1

agent = SACAgent(

    env,
    CktGraph(),
    Actor=GNN().Actor(CktGraph()),
    Critic1=GNN().Critic(CktGraph()),
    Critic2=GNN().Critic(CktGraph()),
    memory_size= memory_size,
    batch_size = batch_size,
    initial_random_steps = initial_random_steps,

)

# train the agent
actor_losses, critic1_losses, critic2_losses, alpha_losses = agent.train(num_steps)

end_time = time.perf_counter()
run_time = end_time - start_time
with open("run_time_log.txt", "a") as log_file:
    log_file.write(f"运行日期： {date} 运行案例： case1 运行算法：SAC 运行时间: {run_time:.2f} 秒\n")

""" Replay the best results """
memory = agent.memory
rews_buf = memory.rews_buf[:num_steps]
info = memory.info_buf[:num_steps]
best_design = np.argmax(rews_buf)
best_action = memory.acts_buf[best_design]
best_reward = np.max(rews_buf)
agent.env.step(best_action)  # run the simulations

results = OutputParser_ota(CktGraph())
op_results = results.dcop('ota_op')

# saved agent's actor and critic network, save memory buffer and agent
save = True
if save == True:
    model_weight_actor = agent.actor.state_dict()
    save_name_actor = f"Actor_{CktGraph().__class__.__name__}_{date}_reward={best_reward:.2f}_{GNN().__class__.__name__}_rew_eng={rew_eng}.pth"

    model_weight_critic1 = agent.critic1.state_dict()
    save_name_critic1 = f"Critic_{CktGraph().__class__.__name__}_{date}_reward={best_reward:.2f}_{GNN().__class__.__name__}_rew_eng={rew_eng}.pth"

    model_weight_critic2 = agent.critic2.state_dict()
    save_name_critic2 = f"Critic_{CktGraph().__class__.__name__}_{date}_reward={best_reward:.2f}_{GNN().__class__.__name__}_rew_eng={rew_eng}.pth"

    torch.save(model_weight_actor, PWD + "/saved_weights_sac/" + save_name_actor)
    torch.save(model_weight_critic1, PWD + "/saved_weights_sac/" + save_name_critic1)
    torch.save(model_weight_critic2, PWD + "/saved_weights_sac/" + save_name_critic2)
    print("Actor and Critic weights have been saved!")

    # save memory
    with open(
            f'./saved_memories_sac/memory_{CktGraph().__class__.__name__}_{date}_reward={best_reward:.2f}_{GNN().__class__.__name__}_rew_eng={rew_eng}.pkl',
            'wb') as memory_file:
        pickle.dump(memory, memory_file)

    np.save(
        f'./saved_memories_sac/rews_buf_{CktGraph().__class__.__name__}_{date}_reward={best_reward:.2f}_{GNN().__class__.__name__}_rew_eng={rew_eng}',
        rews_buf)

    # save agent
    with open(
            f'./saved_agents_sac/SACAgent_{CktGraph().__class__.__name__}_{date}_reward={best_reward:.2f}_{GNN().__class__.__name__}_rew_eng={rew_eng}.pkl',
            'wb') as agent_file:
        pickle.dump(agent, agent_file)

