# AI a Spire - Development Log & Codebase Analysis

**Date:** 2026-02-03

## 1. Executive Summary

Based on an automated analysis of the codebase, this project is a well-structured and surprisingly complete framework for training a Reinforcement Learning (RL) agent to play Slay the Spire. The architecture is robust, leveraging standard machine learning practices and libraries (Gymnasium, Stable-Baselines3).

The most critical finding is that the central question of **defining the Action Space (输出层) is already solved**. The project contains a definitive, atomized, and exhaustive list of all possible actions, complete with mappings to integer IDs and game commands.

The core RL training and execution loop is functional. Areas that require further investigation are the supervised learning pipeline and the rule-based agent's implementation details.

## 2. Project Architecture Overview

The project follows a clear, modern data flow for a game-playing AI:

1.  **Game -> AI**: A custom game mod (presumably `communication mod`) sends the game state as a JSON message to the Python application.
2.  **State Parsing**: `src/core/game_state.py` receives this JSON and parses it into a strongly-typed Python object (`GameState`). This provides a clean, object-oriented representation of the world.
3.  **State Encoding (Input Layer)**: `src/training/encoder.py` takes the `GameState` object and converts it into a numerical vector. This file is the concrete implementation of "State Space" design and is critical for defining the model's **input layer**.
4.  **RL Environment**: `src/env/sts_env.py` wraps the entire process in a standard `gymnasium.Env` interface. It handles the step/reset logic, provides rewards, and crucially, implements **Action Masking** by calculating valid actions for the current state.
5.  **AI Agent Decision**: A trained agent (e.g., from Stable-Baselines3) receives the numerical state vector and the action mask, then chooses an optimal **action ID** (an integer).
6.  **Action Decoding (Output Layer)**: `src/core/action.py` takes the integer **action ID** from the agent, converts it back into a command string (e.g., `"PLAY 0"`), and sends it to the game mod. This file is the concrete implementation of "Action Space" design and defines the model's **output layer**.

## 3. Core Topic Analysis: The Action Space (输出层)

Your primary goal of defining an exhaustive, atomized action space has already been completed within this project.

**Key File:** `src/core/action.py`

This file is the ground truth for the entire Action Space. You should study it carefully.

*   **Definitive List**: The `ActionType` enum and the `Action` class together define every possible atomic action the AI can take. This includes playing cards, using potions, ending the turn, choosing from screens (e.g., card rewards), and interacting with the map.
*   **Fixed Dimension**: The constant `ACTION_SPACE_SIZE` is explicitly defined in this file (with a value of **80**). This is the dimension of your model's output layer. You do not need to guess or calculate it.
*   **Mappings**:
    *   The `to_id()` method provides the mapping from an `Action` object to its unique integer ID (what the model uses).
    *   The `to_command()` method provides the mapping from an `Action` object to the string command sent to the mod.

**Conclusion**: Your task is not to create this space, but to **understand the 80 actions defined in `src/core/action.py`**.

## 4. Project Component Status

*   ### Completed / Functional:
    *   **Core RL Framework**: The environment (`StsEnvironment`), state (`GameState`), action (`Action`), and encoder (`StateEncoder`) components are mature and well-integrated.
    *   **RL Training Pipeline**: `scripts/train_rl.py` is a functional script that uses the `stable-baselines3` library to train an agent (PPO, A2C, DQN) using the `StsEnvironment`. This indicates the project is ready for RL experimentation.
    *   **Interactive Execution**: `scripts/interactive.py` provides a high-level wrapper to run any implemented agent against the game, demonstrating a clean separation of concerns.

*   ### To Be Investigated (Due to Analysis Time Limit):
    *   **Supervised Learning (SL) Pipeline**: The functionality of `scripts/train_sl.py` and the `src/agents/supervised.py` agent was not analyzed.
    *   **Rule-Based Agent**: The logic and completeness of `src/agents/rule_based.py` was not analyzed.
    *   **Configuration**: The full role of `configs/default.yaml` in parameterizing runs was not investigated.
    *   **Data Collection**: The `scripts/collect_data.py` script was not analyzed, but it likely works in tandem with a logger mod like `runlogger`.

## 5. Proposed Next Steps

Instead of designing from scratch, your path is now one of learning and experimentation on an existing, solid foundation.

1.  **Study the Core Files**: Your immediate priority should be to thoroughly read and understand the "four pillars" of the architecture:
    *   `src/core/action.py` (To understand the 80 possible outputs)
    *   `src/core/game_state.py` (To understand the world model)
    *   `src/training/encoder.py` (To understand how the world is turned into numbers for the AI)
    *   `src/env/sts_env.py` (To understand how the RL loop operates)

2.  **Run the Project**: The best way to understand a system is to use it.
    *   Try running `scripts/interactive.py` with the `rule_based` agent (`python scripts/interactive.py --agent-type rule_based`). This will let you see the system in action without needing a trained model.
    *   Attempt to run `scripts/train_rl.py` for a very small number of steps (e.g., `n_steps=128`). This will confirm that your environment setup is correct and all dependencies are working.

3.  **Experiment and Extend**: Once you are comfortable with the existing codebase, you can begin your own work:
    *   **Improve the Encoder**: Modify `src/training/encoder.py` to add new features or try different encoding strategies.
    *   **Tune RL Hyperparameters**: Modify `scripts/train_rl.py` to experiment with different learning rates, network architectures, or other `stable-baselines3` settings.
    *   **Flesh out the SL Pipeline**: If you want to pursue supervised learning, analyze and complete the data collection and training scripts for that pipeline.