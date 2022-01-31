# Game hooks

TODO: write about the general idea.


## List of events and hook signatures

All hooks accept `Game` instance as the first parameter.

For all currently existing hooks, this is the only parameter.
But this signature isn't strictly enforced, because I beleive that other hooks
will require additional parameters in the future.

In this listing, all callbacks have exactly the same names as the corresponding
event names (`"on_turn_start"` and so on).

```python
def on_turn_start(game: Game) -> None:
    """Fired when a player gets control over the `game`, starting a new turn.

    You may choose to interact with the `game` from here (see example below).
    """

def on_turn_end(game: Game) -> None:
    """Fired after getting coins but before giving control to next player.

    *Not* fired after redeploying tokens attacked by another player.

    No acions can be performed from here. This hook is just for observing.
    """

def on_redeploy(game: Game) -> None:
    """Fired when redeploying tokens after being attacked by another player.

    You may choose to put redeployment logic here (see example below).
    """

def on_game_end(game: Game) -> None:
    """Fired after the last turn has ended.

    No acions can be performed from here. This hook is just for observing.
    """
```


## Example of defining hooks

```python
def on_turn_start(game: Game) -> None:
    player_id = game.current_player_id
    print(f"Player {player_id} is starting its turn...")
    ai = ais[player_id]
    ai.do_its_thing(game)

def on_redeploy(game: Game) -> None:
    player_id = game.current_player_id
    ai = ais[player_id]
    ai.redeploy_tokens(game)

hooks = {
    "on_turn_start": on_turn_start,
    "on_redeploy": on_redeploy
}

# After initialization, immediately fires "on_turn_start" for player 0.
game = Game(some, other, args, hooks=hooks)

# Rewards player 0 with Victory Coins.
# Would execute "on_turn_end" if it was defined.
# Then, gives control to player 1 and fires "on_turn_start" immediately.
game.end_turn()

# You get the idea, just call end_turn() n_players*n_turns times.
# You can also do this in "on_turn_start" body,
# but this leads to horrible recursing stack traces.
```


You can find another example of hook definition in
[smawg/cli.py](../smawg/cli.py)

Hooks there are only observing, and the majority of the work is still just
imperative method calls.

This situation will probably change in the future.
