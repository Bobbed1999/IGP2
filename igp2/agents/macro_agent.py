import igp2 as ip
import numpy as np
from typing import List

from igp2.agents.agent import Agent


class MacroAgent(Agent):
    """ Agent executing a pre-defined macro action. Useful for simulating the ego vehicle during MCTS. """

    def __init__(self,
                 agent_id: int,
                 initial_state: ip.AgentState,
                 goal: ip.Goal = None,
                 fps: int = 20):
        """ Create a new macro agent. """
        super().__init__(agent_id, initial_state, goal, fps)
        self._vehicle = ip.KinematicVehicle(initial_state, self.metadata, fps)
        self._current_macro = None
        self._maneuver_end_idx = []

    @property
    def current_macro(self) -> ip.MacroAction:
        """ The current macro action of the agent. """
        return self._current_macro

    @property
    def maneuver_end_idx(self) -> List[int]:
        """ The closed loop trajectory id at which each macro action maneuver completes."""
        return self._maneuver_end_idx

    def done(self, observation: ip.Observation) -> bool:
        """ Returns true if the current macro action has reached a completion state. """
        assert self._current_macro is not None, f"Macro action of Agent {self.agent_id} is None!"
        return self._current_macro.done(observation)

    def next_action(self, observation: ip.Observation) -> ip.Action:
        """ Get the next action from the macro action.

        Args:
            observation: Observation of current environment state and road layout.

        Returns:
            The next action of the agent.
        """

        assert self._current_macro is not None, f"Macro action of Agent {self.agent_id} is None!"

        if self._current_macro.current_maneuver is not None and self._current_macro.current_maneuver.done(observation):
            self._maneuver_end_idx.append(len(self.trajectory_cl.states) - 1)
        action = self._current_macro.next_action(observation)
        return action

    def next_state(self, observation: ip.Observation) -> ip.AgentState:
        """ Get the next action from the macro action and execute it through the attached vehicle of the agent.

        Args:
            observation: Observation of current environment state and road layout.

        Returns:
            The new state of the agent.
        """

        action = self.next_action(observation)
        self.vehicle.execute_action(action)
        return self.vehicle.get_state(observation.frame[self.agent_id].time + 1)

    def reset(self):
        super(MacroAgent, self).reset()
        self._vehicle = ip.KinematicVehicle(self._initial_state, self.metadata, self._fps)
        self._current_macro = None

    def update_macro_action(self,
                            new_macro_action: type(ip.MacroAction),
                            observation: ip.Observation):
        """ Overwrite and initialise current macro action of the agent. If multiple arguments are possible
        for the given macro, then choose the one that brings the agent closest to its goal.

        Args:
            new_macro_action: new macro action to execute
            observation: Current observation of the environment
        """
        frame = observation.frame
        scenario_map = observation.scenario_map
        possible_args = new_macro_action.get_possible_args(frame[self.agent_id], scenario_map, self._goal.center)

        # TODO: Possibly remove this check and consider each turn target separately in MCTS, as this always
        #  selects the turn that takes us closest to the goal which may not be the most optimal
        if len(possible_args) > 1 and isinstance(new_macro_action, type(ip.Exit)):
            ps = np.array([t["turn_target"] for t in possible_args if "turn_target" in t])
            closest = np.argmin(np.linalg.norm(ps - self.goal.center, axis=1))
            possible_args = [{"turn_target": ps[closest]}]

        for kwargs in possible_args:
            self._current_macro = new_macro_action(agent_id=self.agent_id,
                                                   frame=frame,
                                                   scenario_map=scenario_map,
                                                   open_loop=False,
                                                   **kwargs)