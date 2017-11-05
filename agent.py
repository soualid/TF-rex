from dqn import DQN
import numpy as np
import numpy.random as rnd
import random
import tensorflow as tf

class Memory:

    def __init__(self, size):
        self.size = size
        self.mem = np.ndarray((size,5), dtype=object)
        self.iter = 0
        self.current_size = 0

    def remember(self, state1, action, reward, state2, crashed):
        self.mem[self.iter,:] = state1, action, reward, state2, crashed
        self.iter = (self.iter + 1) % self.size
        self.current_size = min(self.current_size + 1, self.size)

    def sample(self, n):
        n = min(self.current_size, n)
        random_idx = random.sample(list(range(self.current_size)), n)
        sample = self.mem[random_idx]
        return (np.stack(sample[:,i], axis=0) for i in range(5))


class DDQNAgent:

    def __init__(self, session, num_actions, width, height, path, writer=None):
        self.path_checkpoints = path
        self.session = session
        self.num_actions = num_actions
        self.memory_size = 10000
        self.explore_prob = 1.
        self.explore_min = 0.01
        self.explore_decay = 0.995
        self.batch_size = 32
        self.discount = .95
        self.memory = Memory(self.memory_size)
        self.main_dqn = DQN(session, height, width, num_actions, "main", writer)
        self.target_dqn = DQN(session, height, width, num_actions, "target", None)
        self.session.run(tf.global_variables_initializer())

        self.update_target_network()
        self.saver = tf.train.Saver()

    def play(self, game, processor):
        self.explore_prob = 0
        ep_steps, ep_reward = 0, 0

        frame,_,crashed = game.start_game()
        frame = processor.process(frame)
        state = np.array([frame, frame, frame, frame])

        while not crashed:
            action,_  = self.act(state)
            next_frame, reward, crashed = game.do_action(action)
            print("action: {}".format(game.actions[action]))
            next_frame = processor.process(next_frame)
            next_state = np.array([*state[-3:], next_frame])

            ep_steps += 1
            ep_reward += reward

        print("---------------------")
        print("CRASH... reward: {}".format(ep_reward))
        print("---------------------\n")
        return ep_steps, ep_reward



    def act(self, state):
        """
        :return: an action and a boolean.
        The returned boolean: - False: action generated by the DQN
                              - True: random action (exploration)
        """
        if self.explore_prob > 0 and rnd.rand() <= self.explore_prob:
            # explore
            return rnd.randint(self.num_actions), True

        return self.main_dqn.get_action(state), False

    def remember(self, state, action, reward, state_next, crashed):
        self.memory.remember(state, action, reward, state_next, crashed)

    def replay(self, cnt):
        if self.memory.current_size < self.batch_size:
            return

        print("...Training...")
        states, actions, rewards, states_next, crashes = self.memory.sample(self.batch_size)
        target = rewards
        # add Q value of next state to not terminal states (i.e. not crashed)
        target[~crashes] += self.discount * self.target_dqn.get_action_and_q(states_next[~crashes])[1]
        self.main_dqn.train(states, actions, target, cnt)

    def explore_less(self):
        self.explore_prob = max(self.explore_min, self.explore_prob * self.explore_decay)

    def update_target_network(self):
        self.target_dqn.tranfer_variables_from(self.main_dqn)

    def save(self, cnt):
        save_path = self.saver.save(self.session, self.path_checkpoints + "rex.ckpt")
        print("Model saved in file: %s" % save_path)

    def load(self, checkpoint_name):
        self.saver.restore(self.session, checkpoint_name)
        print("Model restored")
