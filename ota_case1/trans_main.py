'''
 case3优化模型迁移到case1 DDPG（D-RGCN P-RGCN）
'''
import os
import time
import torch
import pickle
import random
import numpy as np
from datetime import datetime
import gymnasium as gym
from ddpg import DDPGAgent, ReplayBuffer
from ota import OTAEnv
from ckt_graphs import GraphOTA , GraphOTA3
from models import ActorCriticRGCN
from utils import ActionNormalizer, OutputParser_ota
from torch_geometric.nn import TopKPooling, RGCNConv, GCNConv, GATConv, Linear
import torch.nn.functional as F

# # d-rgcn
# old_actor_pth_path = '/home/zk/zhangke/code/ota_case1/saved_weights/Actor_GraphOTA3_OTA3_2024-11-25_noise=uniform_reward=0.81_ActorCriticRGCN_rew_eng=True.pth'
# old_critic_pth_path = '/home/zk/zhangke/code/ota_case1/saved_weights/Critic_GraphOTA3_OTA3_2024-11-25_noise=uniform_reward=0.81_ActorCriticRGCN_rew_eng=True.pth'
# p-rgcn
old_actor_pth_path = '/home/zk/zhangke/code/ota_case1/saved_weights/Actor_GraphOTA3_OTA3_2024-11-23_noise=uniform_reward=0.82_ActorCriticRGCN_rew_eng=True.pth'
old_critic_pth_path = '/home/zk/zhangke/code/ota_case1/saved_weights/Critic_GraphOTA3_OTA3_2024-11-23_noise=uniform_reward=0.82_ActorCriticRGCN_rew_eng=True.pth'
PWD = os.getcwd()
device = GraphOTA().device
CktGraph = GraphOTA
GNN = ActorCriticRGCN
date = datetime.today().strftime('%Y-%m-%d')
rew_eng = CktGraph().rew_eng
# case1 = GraphOTA()
# case3 = GraphOTA3()
#
# # 加载保存的权重
# PWD = "./"  # 项目根目录
# actor_weights = torch.load(PWD + "/saved_weights/Actor_GraphOTA3_OTA3_2024-11-18_noise=uniform_reward=0.81_ActorCriticRGCN_rew_eng=True.pth")
# critic_weights = torch.load(PWD + "/saved_weights/Critic_GraphOTA3_OTA3_2024-11-18_noise=uniform_reward=0.81_ActorCriticRGCN_rew_eng=True.pth")
#
# class GraphPooler(torch.nn.Module):
#     def __init__(self, in_channels, ratio):
#         super(GraphPooler, self).__init__()
#         self.pool = TopKPooling(in_channels, ratio)
#
#     def forward(self, x, edge_index, batch):
#         x, edge_index, _, batch, perm, _ = self.pool(x, edge_index, None, batch)
#         return x, edge_index, batch, perm
#
# class AdjustedActor(torch.nn.Module):
#     def __init__(self, in_channels, num_relations  , out_channels):
#         super(AdjustedActor, self).__init__()
#         self.fc1 = RGCNConv(in_channels, 32, num_relations)
#         self.fc2 = RGCNConv(32, 32, num_relations)
#         self.fc3 = RGCNConv(32, 16, num_relations)
#         self.fc4 = torch.nn.LazyLinear(out_channels)
#
#     def forward(self, state):
#         if len(state.shape) == 2:  # if it is not batched graph data (only one data)
#             state = state.reshape(1, state.shape[0], state.shape[1])
#
#         batch_size = state.shape[0]
#         edge_index = self.edge_index
#         edge_type = self.edge_type
#         device = self.device
#
#         actions = torch.tensor(()).to(device)
#         for i in range(batch_size):
#             x = state[i]
#             x = F.relu(self.conv1(x, edge_index, edge_type))
#             x = F.relu(self.conv2(x, edge_index, edge_type))
#             x = F.relu(self.conv3(x, edge_index, edge_type))
#             x = F.relu(self.conv4(x, edge_index, edge_type))
#             x = self.lin1(torch.flatten(x))
#             x = torch.tanh(x).reshape(1, -1)
#             actions = torch.cat((actions, x), axis=0)
#
#         return actions
#
# class AdjustedCritic(torch.nn.Module):
#     def __init__(self, in_channels, num_relations ,out_channels):
#         super(AdjustedCritic, self).__init__()
#         self.fc1 = RGCNConv(in_channels, 32, num_relations)
#         self.fc2 = RGCNConv(32, 32, num_relations)
#         self.fc3 = RGCNConv(32, 16, num_relations)
#         self.fc4 = torch.nn.LazyLinear(out_channels)
#
#     def forward(self, state, action):
#         batch_size = state.shape[0]
#         edge_index = self.edge_index
#         edge_type = self.edge_type
#         device = self.device
#
#         action = action.repeat_interleave(self.num_nodes, 0).reshape(
#             batch_size, self.num_nodes, -1)
#         data = torch.cat((state, action), axis=2)
#
#         values = torch.tensor(()).to(device)
#         for i in range(batch_size):
#             x = data[i]
#             x = F.relu(self.conv1(x, edge_index, edge_type))
#             x = F.relu(self.conv2(x, edge_index, edge_type))
#             x = F.relu(self.conv3(x, edge_index, edge_type))
#             x = F.relu(self.conv4(x, edge_index, edge_type))
#             x = self.lin1(torch.flatten(x)).reshape(1, -1)
#             values = torch.cat((values, x), axis=0)
#
#         return values
#
# # 初始化池化器
# pooler = GraphPooler(in_channels=case3.num_node_features, ratio=case1.num_nodes / case3.num_nodes)
#
# # 将 case3 图池化
# batch = torch.zeros(20, dtype=torch.long)  # 长度为节点数
# x_pooled, edge_index_pooled, batch_pooled, perm = pooler(case3.obs_shape, case3.edge_index, batch)
#
# # 加载代理
# # with open(f'./saved_agents/DDPGAgent_GraphOTA3_OTA3_2024-11-18_noise=uniform_reward=0.81_ActorCriticRGCN_rew_eng=True.pkl', 'rb') as agent_file:
# #     agent = pickle.load(agent_file)
# #
# # # 加载权重到模型中
# # agent.actor.load_state_dict(actor_weights)
# # agent.critic.load_state_dict(critic_weights)
#
# # 调整Actor和Critic模型的输入层
# adjusted_actor = AdjustedActor(in_channels=case1.num_node_features, num_relations=case3.num_relations , out_channels=case1.action_dim)
# adjusted_critic = AdjustedCritic(in_channels=case1.num_node_features + case1.action_dim, num_relations=case3.num_relations, out_channels=1)
#
# # 将池化后的图输入到调整后的网络中
# x_adjusted, edge_index_adjusted, batch_adjusted, perm_adjusted = pooler(x_pooled, edge_index_pooled, batch_pooled)
# adjusted_actor_output = adjusted_actor(x_adjusted)
# adjusted_critic_output = adjusted_critic(x_adjusted, adjusted_actor_output)
#
# # 迁移Actor和Critic的权重
# adjusted_actor.load_state_dict(actor_weights, strict=False)  # strict=False 允许部分权重不匹配
# adjusted_critic.load_state_dict(critic_weights, strict=False)
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

def transfer_learning(actor_weights, critic_weights, env, case_source, case_target, fine_tune_steps=200):
    # 初始化case1的环境和电路图
    CktGraph = GraphOTA
    GNN = ActorCriticRGCN

    # 初始化Agent
    agent = DDPGAgent(
        env,
        CktGraph(),
        GNN().Actor(CktGraph()),
        GNN().Critic(CktGraph()),
        memory_size,
        batch_size,
        noise_sigma,
        noise_sigma_min,
        noise_sigma_decay,
        initial_random_steps=initial_random_steps,
        noise_type=noise_type,
    )
    # transition = list()
    # memory = ReplayBuffer(CktGraph, memory_size, batch_size)
    agent.actor.load_state_dict(actor_weights, strict=False)
    agent.critic.load_state_dict(critic_weights, strict=False)

    # 可选：加载Replay Memory
    # try:
    #     memory = load_memory(case_source)
    #     agent.memory = memory
    # except FileNotFoundError:
    #     print("No memory found, starting with empty memory.")

    # 微调200步
    rewards = []
    for step in range(fine_tune_steps):
        state, info = env.reset()
        total_reward = 0
        episode = 0  # 记录episode数量

        while True:  # 无限循环，直到满足条件
            action = agent.select_action(state)
            next_state, reward, terminated, truncated, info = agent.step(action)
            state = next_state

            # 更新Agent
            if (
                len(agent.memory) >= batch_size
            ):
              agent.update_model()
              state = next_state
              total_reward += reward

            # 如果episode结束，退出循环
            if reward > 0:
                episode += 1
                break

        # 记录每个微调步的总奖励
        rewards.append(total_reward)
        print(f"Fine-tuning Step {step + 1}/{fine_tune_steps}, Episode: {episode}, Reward: {total_reward:.2f}")

    # 打印微调完成提示
    print("Fine-tuning completed.")

    # 保存微调后的模型
    date = datetime.now().strftime("%Y%m%d")
    save_name_actor = f"Actor_{case_target}_{date}_fine_tuned.pth"
    save_name_critic = f"Critic_{case_target}_{date}_fine_tuned.pth"
    torch.save(agent.actor.state_dict(), PWD + "/saved_weights/" + save_name_actor)
    torch.save(agent.critic.state_dict(), PWD + "/saved_weights/" + save_name_critic)
    print(f"Fine-tuned models saved: {save_name_actor}, {save_name_critic}")

    return rewards

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
noise_sigma = 2  # noise volume
noise_sigma_min = 0.1
noise_sigma_decay = 0.999  # if 1 means no decay
initial_random_steps = 0
noise_type = 'uniform'

# 加载Replay Memory（可选）
# def load_memory(case_name):
#     memory_path = f"{SAVED_MEMORIES_DIR}memory_{case_name}.pkl"
#     with open(memory_path, 'rb') as file:
#         memory = pickle.load(file)
#     return memory

# 定义迁移学习微调流程


# 执行迁移学习任务
case3_name = "case3"
case1_name = "case1"
actor_weights = Adjustactor(old_pth_path=old_actor_pth_path, device=device)
critic_weights = Adjustcritic(old_pth_path=old_critic_pth_path, device=device)

agent = DDPGAgent(
        env,
        CktGraph(),
        GNN().Actor(CktGraph()),
        GNN().Critic(CktGraph()),
        memory_size,
        batch_size,
        noise_sigma,
        noise_sigma_min,
        noise_sigma_decay,
        initial_random_steps=initial_random_steps,
        noise_type=noise_type,
    )
    # transition = list()
    # memory = ReplayBuffer(CktGraph, memory_size, batch_size)
agent.actor.load_state_dict(actor_weights, strict=False)
agent.critic.load_state_dict(critic_weights, strict=False)
agent.train(num_steps)

end_time = time.perf_counter()
run_time = end_time - start_time
with open("run_time_log.txt", "a") as log_file:
    log_file.write(f"运行日期： {date} 案例： case1 实验类型：trans 运行时间: {run_time:.2f} 秒\n")

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
        save_name_actor = f"Actor_trans_{CktGraph().__class__.__name__}_{date}_noise={noise_type}_reward={best_reward:.2f}_{GNN().__class__.__name__}_rew_eng={rew_eng}.pth"

        model_weight_critic = agent.critic.state_dict()
        save_name_critic = f"Critic_trans_{CktGraph().__class__.__name__}_{date}_noise={noise_type}_reward={best_reward:.2f}_{GNN().__class__.__name__}_rew_eng={rew_eng}.pth"

        torch.save(model_weight_actor, PWD + "/saved_weights/" + save_name_actor)
        torch.save(model_weight_critic, PWD + "/saved_weights/" + save_name_critic)
        print("Actor and Critic weights have been saved!")

        # save memory
        with open(
                f'./saved_memories/memory_trans_{CktGraph().__class__.__name__}_{date}_noise={noise_type}_reward={best_reward:.2f}_{GNN().__class__.__name__}_rew_eng={rew_eng}.pkl',
                'wb') as memory_file:
            pickle.dump(memory, memory_file)

        np.save(
            f'./saved_memories/rews_buf_trans_{CktGraph().__class__.__name__}_{date}_noise={noise_type}_reward={best_reward:.2f}_{GNN().__class__.__name__}_rew_eng={rew_eng}',
            rews_buf)

        # save agent
        with open(
                f'./saved_agents/DDPGAgent_trans_{CktGraph().__class__.__name__}_{date}_noise={noise_type}_reward={best_reward:.2f}_{GNN().__class__.__name__}_rew_eng={rew_eng}.pkl',
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
