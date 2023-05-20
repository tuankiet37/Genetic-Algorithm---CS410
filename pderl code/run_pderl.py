import numpy as np, os, time, random
from core import mod_utils as utils, agent
import gym, torch
import argparse
import pickle
from core.operator_runner import OperatorRunner
from parameters import Parameters

parser = argparse.ArgumentParser()
parser.add_argument('-env', help='Environment Choices: (Swimmer-v2) (HalfCheetah-v2) (Hopper-v2) ' +
                                 '(Walker2d-v2) (Ant-v2)', required=True, type=str)
parser.add_argument('-seed', help='Random seed to be used', type=int, default=7)
parser.add_argument('-disable_cuda', help='Disables CUDA', action='store_true')
parser.add_argument('-render', help='Render gym episodes', action='store_true')
parser.add_argument('-sync_period', help="How often to sync to population", type=int)
parser.add_argument('-novelty', help='Use novelty exploration', action='store_true')
parser.add_argument('-proximal_mut', help='Use safe mutation', action='store_true')
parser.add_argument('-distil', help='Use distilation crossover', action='store_true')
parser.add_argument('-distil_type', help='Use distilation crossover. Choices: (fitness) (distance)',
                    type=str, default='fitness')
parser.add_argument('-per', help='Use Prioritised Experience Replay', action='store_true')
parser.add_argument('-mut_mag', help='The magnitude of the mutation', type=float, default=0.05)
parser.add_argument('-mut_noise', help='Use a random mutation magnitude', action='store_true')
parser.add_argument('-verbose_mut', help='Make mutations verbose', action='store_true')
parser.add_argument('-verbose_crossover', help='Make crossovers verbose', action='store_true')
parser.add_argument('-logdir', help='Folder where to save results', type=str, required=True)
parser.add_argument('-opstat', help='Store statistics for the variation operators', action='store_true')
parser.add_argument('-opstat_freq', help='Frequency (in generations) to store operator statistics', type=int, default=1)
parser.add_argument('-save_periodic', help='Save actor, critic and memory periodically', action='store_true')
parser.add_argument('-next_save', help='Generation save frequency for save_periodic', type=int, default=200)
parser.add_argument('-test_operators', help='Runs the operator runner to test the operators', action='store_true')
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


if __name__ == "__main__":
    parameters = Parameters(parser)  # Inject the cla arguments in the parameters object
    tracker = utils.Tracker(parameters, ['erl'], '_score.csv')  # Initiate tracker
    frame_tracker = utils.Tracker(parameters, ['frame_erl'], '_score.csv')  # Initiate tracker
    time_tracker = utils.Tracker(parameters, ['time_erl'], '_score.csv')
    ddpg_tracker = utils.Tracker(parameters, ['ddpg'], '_score.csv')
    selection_tracker = utils.Tracker(parameters, ['elite', 'selected', 'discarded'], '_selection.csv')

    # Create Env
    env = utils.NormalizedActions(gym.make(parameters.env_name))
    parameters.action_dim = env.action_space.shape[0]
    parameters.state_dim = env.observation_space.shape[0]

    # Write the parameters to a the info file and print them
    parameters.write_params(stdout=True)

    # Seed
    env.seed(parameters.seed)
    torch.manual_seed(parameters.seed)
    np.random.seed(parameters.seed)
    random.seed(parameters.seed)

    # Tests the variation operators after that is saved first with -save_periodic
    if parameters.test_operators:
        operator_runner = OperatorRunner(parameters, env)
        operator_runner.run()
        exit()

    # Create Agent
    agent = agent.Agent(parameters, env)
    print('Running', parameters.env_name, ' State_dim:', parameters.state_dim, ' Action_dim:', parameters.action_dim)

    next_save = parameters.next_save; time_start = time.time()
    while agent.num_frames <= parameters.num_frames:
        stats = agent.train()
        best_train_fitness = stats['best_train_fitness']
        erl_score = stats['test_score']
        elite_index = stats['elite_index']
        ddpg_reward = stats['ddpg_reward']
        policy_gradient_loss = stats['pg_loss']
        behaviour_cloning_loss = stats['bc_loss']
        population_novelty = stats['pop_novelty']

        print('#Games:', agent.num_games, '#Frames:', agent.num_frames, '#Parameters frame: ',parameters.num_frames,
              ' Train_Max:', '%.2f'%best_train_fitness if best_train_fitness is not None else None,
              ' Test_Score:','%.2f'%erl_score if erl_score is not None else None,
              ' Avg:','%.2f'%tracker.all_tracker[0][1],
              ' ENV:  '+ parameters.env_name,
              ' DDPG Reward:', '%.2f'%ddpg_reward,
              ' PG Loss:', '%.4f' % policy_gradient_loss)

        elite = agent.evolver.selection_stats['elite']/agent.evolver.selection_stats['total']
        selected = agent.evolver.selection_stats['selected'] / agent.evolver.selection_stats['total']
        discarded = agent.evolver.selection_stats['discarded'] / agent.evolver.selection_stats['total']

        print()
        tracker.update([erl_score], agent.num_games)
        frame_tracker.update([erl_score], agent.num_frames)
        time_tracker.update([erl_score], time.time()-time_start)
        ddpg_tracker.update([ddpg_reward], agent.num_frames)
        selection_tracker.update([elite, selected, discarded], agent.num_frames)

        # Save Policy
        if agent.num_games > next_save:
            next_save += parameters.next_save
            if elite_index is not None:
                torch.save(agent.pop[elite_index].actor.state_dict(), os.path.join(parameters.save_foldername,
                                                                                   'evo_net.pkl'))

                if parameters.save_periodic:
                    save_folder = os.path.join(parameters.save_foldername, 'models')
                    if not os.path.exists(save_folder):
                        os.makedirs(save_folder)

                    actor_save_name = os.path.join(save_folder, 'evo_net_actor_{}.pkl'.format(next_save))
                    critic_save_name = os.path.join(save_folder, 'evo_net_critic_{}.pkl'.format(next_save))
                    buffer_save_name = os.path.join(save_folder, 'champion_buffer_{}.pkl'.format(next_save))

                    torch.save(agent.pop[elite_index].actor.state_dict(), actor_save_name)
                    torch.save(agent.rl_agent.critic.state_dict(), critic_save_name)
                    with open(buffer_save_name, 'wb+') as buffer_file:
                        pickle.dump(agent.rl_agent.buffer, buffer_file)

            print("Progress Saved")











