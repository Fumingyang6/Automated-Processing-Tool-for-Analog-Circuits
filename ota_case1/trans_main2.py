'''
 case3优化模型迁移到case1 SAC（D-RGCN P-RGCN）
'''
import os
import time
import torch
import pickle
import random
import numpy as np
from datetime import datetime
import gymnasium as gym
from sac import SACAgent,ReplayBuffer
from ota import OTAEnv
from ckt_graphs import GraphOTA , GraphOTA3
from models import ActorCriticRGCN
from utils import ActionNormalizer, OutputParser_ota
from torch_geometric.nn import TopKPooling, RGCNConv, GCNConv, GATConv, Linear
import torch.nn.functional as F

# d-rgcn
# old_actor_pth_path = '/home/zk/zhangke/code/ota_case1/saved_weights_sac/Actor_GraphOTA3_2024-11-24_OTA3_reward=0.81_ActorCriticRGCN_rew_eng=True.pth'
# old_critic_pth_path = '/home/zk/zhangke/code/ota_case1/saved_weights_sac/Critic_GraphOTA3_2024-11-24_OTA3_reward=0.81_ActorCriticRGCN_rew_eng=True.pth'
# p-rgcn
old_actor_pth_path = '/home/zk/zhangke/code/ota_case1/saved_weights_sac/Actor_GraphOTA3_2024-11-22_OTA3_reward=0.85_ActorCriticRGCN_rew_eng=True.pth'
old_critic_pth_path = '/home/zk/zhangke/code/ota_case1/saved_weights_sac/Critic_GraphOTA3_2024-11-22_OTA3_reward=0.85_ActorCriticRGCN_rew_eng=True.pth'
PWD = os.getcwd()
device = GraphOTA().device
CktGraph = GraphOTA
GNN = ActorCriticRGCN
date = datetime.today().strftime('%Y-%m-%d')
rew_eng = CktGraph().rew_eng

def Adjustactor(old_pth_path, device):
    with open(old_pth_path,'rb') as f:
        data = torch.load(f)
    old_lin1_weight = data['lin1.weight']
    old_lin1_bias = data['lin1.bias']

    new_weight_shape = (13, 176)
    new_bias_shape = (13,)

    min_value = torch.min(old_lin1_weight).item()
    max_value = torch.max(old_lin1_weight).item()
    new_weight = torch.tensor([
        [random.uniform(min_value, max_value) for _ in range(new_weight_shape[1])]
        for _ in range(new_weight_shape[0])
    ], dtype=torch.float32)
    new_weight = new_weight.to(device)

    min_bias = torch.min(old_lin1_bias).item()
    max_bias = torch.max(old_lin1_bias).item()
    new_bias = torch.tensor([
        random.uniform(min_bias, max_bias) for _ in range(new_bias_shape[0])
    ], dtype=torch.float32)
    new_bias = new_bias.to(device)

    data['lin1.weight'] = new_weight
    data['lin1.bias'] = new_bias

    return data

def Adjustcritic(old_pth_path,device):
    with open(old_pth_path,'rb') as f:
        data3 = torch.load(f)
    old_conv1_weight = data3['conv1.weight']
    old_conv1_root = data3['conv1.root']
    old_lin_weight = data3['lin1.weight']

    new_conv1_weight_shape = (32, 26, 32)
    new_conv1_root_shape = (26, 32)
    new_lin_weight_shape = (1, 176)

    # 创建新的 conv1.weight 张量
    min_value1 = torch.min(old_conv1_weight).item()
    max_value1 = torch.max(old_conv1_weight).item()
    new_conv1_weight = torch.tensor([
        [[random.uniform(min_value1, max_value1) for _ in range(new_conv1_weight_shape[2])]
         for _ in range(new_conv1_weight_shape[1])]
        for _ in range(new_conv1_weight_shape[0])
    ], dtype=torch.float32)
    new_conv1_weight = new_conv1_weight.to(device)

    # 创建新的 conv1.root 张量
    min_value2 = torch.min(old_conv1_root).item()
    max_value2 = torch.max(old_conv1_root).item()
    new_conv1_root = torch.tensor([
        [random.uniform(min_value2, max_value2) for _ in range(new_conv1_root_shape[1])]
        for _ in range(new_conv1_root_shape[0])
    ], dtype=torch.float32)
    new_conv1_root = new_conv1_root.to(device)

    # 创建新的 lin1.weight 张量
    min_value3 = torch.min(old_lin_weight).item()
    max_value3 = torch.max(old_lin_weight).item()
    new_lin_weight = torch.tensor([
        [random.uniform(min_value3, max_value3) for _ in range(new_lin_weight_shape[1])]
        for _ in range(new_lin_weight_shape[0])
    ], dtype=torch.float32)
    new_lin_weight = new_lin_weight.to(device)

    # 替换原始权重
    data3['conv1.weight'] = new_conv1_weight
    data3['conv1.root'] = new_conv1_root
    data3['lin1.weight'] = new_lin_weight

    return data3

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
start_time = time.perf_counter()
# parameters
num_steps = 200
memory_size = 200
batch_size = 10
initial_random_steps = 0


# 执行迁移学习任务
case3_name = "case3"
case1_name = "case1"
actor_weights = Adjustactor(old_pth_path=old_actor_pth_path, device=device)
critic_weights = Adjustcritic(old_pth_path=old_critic_pth_path, device=device)

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


agent.actor.load_state_dict(actor_weights, strict=False)
agent.critic1.load_state_dict(critic_weights, strict=False)
agent.critic2.load_state_dict(critic_weights, strict=False)
# train the agent
actor_losses, critic1_losses, critic2_losses, alpha_losses = agent.train(num_steps)

end_time = time.perf_counter()
run_time = end_time - start_time
with open("run_time_log.txt", "a") as log_file:
    log_file.write(f"运行日期： {date} 案例： case1 实验类型：trans2 运行时间: {run_time:.2f} 秒\n")

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
    save_name_actor = f"Actor_trans2_{CktGraph().__class__.__name__}_{date}_OTA3_reward={best_reward:.2f}_{GNN().__class__.__name__}_rew_eng={rew_eng}.pth"

    model_weight_critic1 = agent.critic1.state_dict()
    save_name_critic1 = f"Critic1_trans2_{CktGraph().__class__.__name__}_{date}_OTA3_reward={best_reward:.2f}_{GNN().__class__.__name__}_rew_eng={rew_eng}.pth"

    model_weight_critic2 = agent.critic2.state_dict()
    save_name_critic2 = f"Critic2_trans2_{CktGraph().__class__.__name__}_{date}_OTA3_reward={best_reward:.2f}_{GNN().__class__.__name__}_rew_eng={rew_eng}.pth"

    torch.save(model_weight_actor, PWD + "/saved_weights_sac/" + save_name_actor)
    torch.save(model_weight_critic1, PWD + "/saved_weights_sac/" + save_name_critic1)
    torch.save(model_weight_critic2, PWD + "/saved_weights_sac/" + save_name_critic2)
    print("Actor and Critic weights have been saved!")

    # save memory
    with open(
            f'./saved_memories_sac/memory_trans2_{CktGraph().__class__.__name__}_{date}_OTA3_reward={best_reward:.2f}_{GNN().__class__.__name__}_rew_eng={rew_eng}.pkl',
            'wb') as memory_file:
        pickle.dump(memory, memory_file)

    np.save(
        f'./saved_memories_sac/rews_buf_trans2_{CktGraph().__class__.__name__}_{date}_OTA3_reward={best_reward:.2f}_{GNN().__class__.__name__}_rew_eng={rew_eng}',
        rews_buf)

    # save agent
    with open(
            f'./saved_agents_sac/SACAgent_trans2_{CktGraph().__class__.__name__}_{date}_OTA3_reward={best_reward:.2f}_{GNN().__class__.__name__}_rew_eng={rew_eng}.pkl',
            'wb') as agent_file:
        pickle.dump(agent, agent_file)

# rewards = transfer_learning(actor_weights, critic_weights, case_source=case3_name, case_target=case1_name, fine_tune_steps=200)
#
# # 可视化Reward变化（可选）
# import matplotlib.pyplot as plt
# plt.plot(rewards)
# plt.xlabel("Training Step")
# plt.ylabel("Reward")
# plt.title("Reward during Fine-tuning on Case1")
# plt.show()
