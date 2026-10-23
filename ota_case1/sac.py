# 处理离散问题的模型
import numpy as np

from typing import List, Tuple, Dict
from copy import deepcopy

import torch
from torch.nn import LazyLinear
import torch.nn.functional as F
import torch.optim as optim
from utils import ActionNormalizer,OutputParser_ota
import numpy as np

from utils import trunc_normal

from IPython.display import clear_output
import matplotlib.pyplot as plt


# ----------------------------------------- #
# 经验回放池
# ----------------------------------------- #

class ReplayBuffer:  # 进行一个已有数据信息的缓存，缓存区的数据经过采样可以加速算法收敛
    """A simple numpy replay buffer."""

    def __init__(self, CktGraph, size: int, batch_size: int = 32):

        self.num_node_features = CktGraph.num_node_features
        self.action_dim = CktGraph.action_dim
        self.num_nodes = CktGraph.num_nodes

        """Initializate."""
        self.obs_buf = np.zeros(
            [size, self.num_nodes, self.num_node_features], dtype=np.float32)
        self.next_obs_buf = np.zeros(
            [size, self.num_nodes, self.num_node_features], dtype=np.float32)
        self.acts_buf = np.zeros([size, self.action_dim], dtype=np.float32)
        self.rews_buf = np.zeros([size], dtype=np.float32)
        self.done_buf = np.zeros([size], dtype=np.float32)
        self.info_buf = np.zeros([size], dtype=object) # store the performance of LDO in each step
        self.max_size, self.batch_size = size, batch_size
        self.ptr, self.size, = 0, 0

    def store(
        self,
        obs: np.ndarray,
        act: np.ndarray,
        rew: float,
        next_obs: np.ndarray,
        done: bool,
        info: dict,
    ):
        """Store the transition in buffer."""
        self.obs_buf[self.ptr] = obs
        self.next_obs_buf[self.ptr] = next_obs
        self.acts_buf[self.ptr] = act
        self.rews_buf[self.ptr] = rew
        self.done_buf[self.ptr] = done
        self.info_buf[self.ptr] = info # store the performance of LDO in each step
        self.ptr = (self.ptr + 1) % self.max_size
        self.size = min(self.size + 1, self.max_size)

    def sample_batch(self) -> Dict[str, np.ndarray]:
        """Randomly sample a batch of experiences from memory."""
        idxs = np.random.choice(self.size, size=self.batch_size, replace=False)
        return dict(obs=self.obs_buf[idxs],
                    next_obs=self.next_obs_buf[idxs],
                    acts=self.acts_buf[idxs],
                    rews=self.rews_buf[idxs],
                    done=self.done_buf[idxs])

    def __len__(self) -> int:
        return self.size

# ----------------------------------------- #
# 模型构建
# ----------------------------------------- #


    """SACAgent interacting with environment.

    Attributes:
     env (gym.Env): OpenAI Gym environment.
     actor (nn.Module): stochastic policy (actor) model to select actions based on a probability distribution.
     actor_optimizer (Optimizer): optimizer for training the actor network.
     critic_1 (nn.Module): first critic model to evaluate state-action value (Q-value).
     critic_2 (nn.Module): second critic model to reduce overestimation bias (double Q-learning).
     critic_target_1 (nn.Module): first target critic model for stabilizing critic updates.
     critic_target_2 (nn.Module): second target critic model for stabilizing critic updates.
     critic_optimizer_1 (Optimizer): optimizer for training the first critic.
     critic_optimizer_2 (Optimizer): optimizer for training the second critic.
     alpha (float): entropy coefficient for balancing exploration and exploitation.
     alpha_optimizer (Optimizer): optimizer for updating the entropy coefficient (alpha), if automatic entropy tuning is enabled.
     target_entropy (float): target entropy used to guide the stochasticity of the policy.
     memory (ReplayBuffer): replay memory to store experience transitions (state, action, reward, next_state, done).
     batch_size (int): batch size for sampling experiences from the replay buffer.
     gamma (float): discount factor to balance short-term and long-term rewards.
     tau (float): parameter for soft target updates of the critic networks.
     initial_random_steps (int): initial steps where random actions are taken before the policy is learned.
     device (torch.device): device for computation (CPU / GPU).
     transition (list): temporary storage for the current transition (state, action, reward, next_state, done).
     total_step (int): total number of steps taken by the agent during training.
     is_test (bool): flag indicating whether the agent is in training or testing mode.
     automatic_entropy_tuning (bool): flag indicating whether entropy coefficient is automatically tuned.
     log_alpha (torch.Tensor): learnable log of alpha for automatic entropy tuning.
     policy_update_interval (int): frequency of policy (actor) updates compared to critic updates.
   """

class SACAgent:
    def __init__(
                self,
                env,
                CktGraph,
                Actor,
                Critic1,
                Critic2,
                memory_size: int,
                batch_size: int,
                gamma: float = 0.99,
                tau: float = 5e-3,
                alpha: float = 0.2,
                automatic_entropy_tuning: bool = True,
                target_entropy: float = -3,
                actor_lr: float = 3e-4,
                critic_lr: float = 3e-4,
                alpha_lr: float = 3e-4,
                initial_random_steps: int = 1e4
        ):
            super().__init__()
            """Initialize."""
            self.env = env
            self.memory = ReplayBuffer(CktGraph, memory_size, batch_size)
            self.batch_size = batch_size
            self.gamma = gamma
            self.tau = tau
            self.initial_random_steps = initial_random_steps
            self.episode = 0

            self.device = CktGraph.device
            print(self.device)

            self.automatic_entropy_tuning = automatic_entropy_tuning
            self.target_entropy = target_entropy

            # Action dimension and target entropy
            self.action_dim = CktGraph.action_dim
            if automatic_entropy_tuning: # 是否使用alpha训练求梯度
                self.log_alpha = torch.zeros(1, requires_grad=True, device=self.device)
                self.alpha_optimizer = optim.Adam([self.log_alpha], lr=alpha_lr)
            else:
                self.alpha = alpha

            # networks 实例化网络
            self.actor = Actor.to(self.device)
            self.actor_optimizer = optim.Adam(self.actor.parameters(), lr=actor_lr, weight_decay=1e-4)

            self.critic1 = Critic1.to(self.device)
            self.critic2 = Critic2.to(self.device)
            self.critic_target1 = deepcopy(self.critic1)
            self.critic_target2 = deepcopy(self.critic2)

            self.critic_optimizer1 = optim.Adam(self.critic1.parameters(), lr=critic_lr, weight_decay=1e-4)
            self.critic_optimizer2 = optim.Adam(self.critic2.parameters(), lr=critic_lr, weight_decay=1e-4)

            # transition to store in memory
            self.transition = list()

            # total steps count
            self.total_step = 0

            # mode: train / test
            self.is_test = False

            self.action_space_low = np.array([1, 0.5, 1,
                                              1, 0.5, 1,
                                              1, 0.5, 1,
                                              1, 0.5, 1,
                                              0.9,  # vb
                                              ])

            self.action_space_high = np.array([100, 1.5, 10,
                                               100, 1.5, 10,
                                               100, 1.5, 10,
                                               100, 1.5, 10,
                                               1.4,
                                               ])


    def select_action(self, state: np.ndarray) -> np.ndarray:
            """Select an action from the input state."""
            if self.is_test == False:
                if self.total_step < self.initial_random_steps:  # random actions at the start
                    print('*** Random actions ***')
                    selected_action = np.random.uniform(-1, 1, self.action_dim)
                else:
                    print('*** SAC policy actions ***')
                    selected_action = self.actor(
                        torch.FloatTensor(state).to(self.device)
                    ).detach().cpu().numpy()  # in (-1, 1),这里是否需要设置deterministic = True有待确定
                    selected_action = selected_action.flatten()

            else:
                selected_action, _ = self.actor(
                    torch.FloatTensor(state).to(self.device)
                )
                selected_action = selected_action.detach().cpu().numpy()

            print(f'selected action: {selected_action}')
            self.transition = [state, selected_action]

            return selected_action

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, np.float64, bool]:
            """Take an action and return the response of the env."""
            # self.env.set_total_step(self.total_step)  #  运行main3.py时启用
            next_state, reward, terminated, truncated, info = self.env.step(action)

            if self.is_test == False:
                self.transition += [reward, next_state, terminated, info]
                self.memory.store(*self.transition)

            return next_state, reward, terminated, truncated, info

    def update_model(self) -> torch.Tensor:
            print("*** Update the model by gradient descent. ***")
            """Update the model by gradient descent."""
            device = self.device  # for shortening the following lines

            samples = self.memory.sample_batch()
            state = torch.FloatTensor(samples["obs"]).to(device)
            next_state = torch.FloatTensor(samples["next_obs"]).to(device)
            action = torch.FloatTensor(samples["acts"]).to(device)
            reward = torch.FloatTensor(samples["rews"].reshape(-1, 1)).to(device)
            done = torch.FloatTensor(samples["done"].reshape(-1, 1)).to(device)

            masks = 1 - done

            # 避免首次调用alpha时报错的情况
            if hasattr(self, 'log_alpha'):
                # self.alpha = self.log_alpha.exp()  # 动态计算 alpha
                self.alpha = torch.clamp(torch.exp(self.log_alpha), min=1e-5, max=1e1)

            else:
                self.alpha = self.alpha  # 使用初始常量 alpha

            # with torch.no_grad():
            #     # next_action, next_log_prob = self.actor(next_state)
            #     next_action = self.actor(next_state)
            #     _next_probs = self.actor(next_state)
            #     next_probs = ActionNormalizer(action_space_low=self.action_space_low, action_space_high= \
            #         self.action_space_high).action(_next_probs)  # convert [-1.1] range back to normal range
            #     next_log_prob = torch.log(torch.from_numpy(next_probs)) # 避免next_log_prob出现负数：使用归一化之后的数值或直接置零
            #     next_log_prob = next_log_prob.to('cuda:0')
            #     # next_log_prob = torch.log(next_action + 1e-8)
            #     next_q1 = self.critic_target1(next_state, next_action)
            #     next_q2 = self.critic_target2(next_state, next_action)
            #     next_q_value = torch.min(next_q1, next_q2) - self.alpha * next_log_prob
            #     curr_return = reward + self.gamma * next_q_value * masks
            with torch.no_grad():
                # 1. 获取 next action
                next_action = self.actor(next_state)

                # 2. 归一化并取 log prob
                _next_probs = self.actor(next_state)
                next_probs = ActionNormalizer(
                    action_space_low=self.action_space_low,
                    action_space_high=self.action_space_high
                ).action(_next_probs)  # shape: [128, num_nodes, action_dim]

                # 将 numpy 转成 tensor，并防止 log(0)
                next_probs = torch.from_numpy(next_probs).to('cuda:0') + 1e-8
                next_log_prob = torch.log(next_probs)  # shape: [128, num_nodes, action_dim]

                # 3. 聚合 log prob 使其与 Q 值维度匹配
                next_log_prob = next_log_prob.sum(dim=1, keepdim=True)  # shape: [128, 1]

                # 4. 获取 target Q 值
                next_q1 = self.critic_target1(next_state, next_action)  # shape: [128, 1]
                next_q2 = self.critic_target2(next_state, next_action)  # shape: [128, 1]
                next_q_value = torch.min(next_q1, next_q2) - self.alpha * next_log_prob  # shape: [128, 1]

                # 5. 计算目标 return
                curr_return = reward + self.gamma * next_q_value * masks  # shape: [128, 1]

            # train critic
            curr_q1 = self.critic1(state, action)
            curr_q2 = self.critic2(state, action)
            curr_q1 = curr_q1.float()
            curr_q2 = curr_q2.float()
            curr_return = curr_return.float()
            critic1_loss = F.mse_loss(curr_q1, curr_return)
            critic2_loss = F.mse_loss(curr_q2, curr_return)

            self.critic_optimizer1.zero_grad()
            critic1_loss.backward()
            self.critic_optimizer1.step()

            self.critic_optimizer2.zero_grad()
            critic2_loss.backward()
            self.critic_optimizer2.step()

            # train actor
            new_action = self.actor(state)
            _new_prob = self.actor(state)
            new_probs = ActionNormalizer(action_space_low=self.action_space_low, action_space_high= \
                self.action_space_high).action(_new_prob)  # convert [-1.1] range back to normal range
            log_prob = torch.log(torch.from_numpy(new_probs))  # 避免next_log_prob出现负数
            log_prob = log_prob.to('cuda:0')
            # log_prob = torch.log(new_action + 1e-8)
            q1 = self.critic1(state, new_action)
            q2 = self.critic2(state, new_action)
            q_value = torch.min(q1, q2)

            actor_loss = (self.alpha * log_prob - q_value).mean()

            self.actor_optimizer.zero_grad()
            actor_loss.backward()
            self.actor_optimizer.step()

            # update alpha
            if self.automatic_entropy_tuning:
                alpha_loss = -(self.log_alpha * (log_prob + self.target_entropy).detach()).mean()
                self.alpha_optimizer.zero_grad()
                alpha_loss.backward()
                self.alpha_optimizer.step()
            else:
                alpha_loss = torch.tensor(0.)

            # target networks soft update
            self._target_soft_update()

            return actor_loss.item(), critic1_loss.item(), critic2_loss.item(), alpha_loss.item()

    def train(self, num_steps: int, plotting_interval: int = 500):
            """Train the agent."""
            self.is_test = False

            state, info = self.env.reset()
            actor_losses, critic1_losses, critic2_losses, alpha_losses, scores = [], [], [], [], []
            score = 0

            for self.total_step in range(1, num_steps + 1):
                print(f'*** Step: {self.total_step} | Episode: {self.episode} ***')

                action = self.select_action(state)
                next_state, reward, terminated, truncated, info = self.step(action)

                state = next_state
                score += reward

                if terminated or truncated:
                    state, info = self.env.reset()
                    self.episode = self.episode + 1
                    scores.append(score)
                    score = 0

                if (
                        len(self.memory) >= self.batch_size
                        and self.total_step > self.initial_random_steps
                ):
                    actor_loss, critic1_loss, critic2_loss, alpha_loss = self.update_model()
                    actor_losses.append(actor_loss)
                    critic1_losses.append(critic1_loss)
                    critic2_losses.append(critic2_loss)
                    alpha_losses.append(alpha_loss)

            self.env.close()
            return actor_losses, critic1_losses, critic2_losses, alpha_losses

    def test(self):
            """Test the agent."""
            self.is_test = True

            state, info = self.env.reset()
            truncated = False
            terminated = False
            score = 0
            performance_list = []

            while not (truncated or terminated):
                action = self.select_action(state)
                next_state, reward, terminated, truncated, info = self.step(action)
                performance_list.append([action, info])

                state = next_state
                score += reward

            print(f"score: {score}")
            print(f"info: {info}")
            self.env.close()

            return performance_list

    def _target_soft_update(self):
            """Soft-update: target = tau*local + (1-tau)*target."""
            tau = self.tau

            for t_param, l_param in zip(self.critic_target1.parameters(), self.critic1.parameters()):
                t_param.data.copy_(tau * l_param.data + (1.0 - tau) * t_param.data)

            for t_param, l_param in zip(self.critic_target2.parameters(), self.critic2.parameters()):
                t_param.data.copy_(tau * l_param.data + (1.0 - tau) * t_param.data)





