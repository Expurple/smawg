# Game hooks

Hooks are supposed to provide an ergonomic way to act on specific game events,
rather than manually check the game state after every action to see if that
event has occured. Initially I implemented them to simplify `smawg.cli`.

However, over time I've discovered that using them
brings weird dependencies to the code and complicates control flow.
By 0.14.0, `smawg.cli` stopped using hooks. I no longer recommend using them.
But here they are in case you find then useful.

## List of events and hook signatures

All hooks accept `Game` instance as the first parameter.
Some also accept additional info about the event.

In this listing, all callbacks have exactly the same names as the corresponding
event names (`"on_turn_start"` and so on).

```python
def on_turn_start(game: Game) -> None:
    """Fired when a player gets control over the `game`, starting a new turn.

    You may choose to interact with the `game` from here (see example below).
    """

def on_dice_rolled(game: Game, value: int, conquest_success: bool) -> None:
    """Fired after an attempt to conquer a region using the reinforcement dice.

    This hook is intended just for notifying about
    the dice `value` and `conquest_success`.
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

In this example, game actions are performed exclusively from inside hooks.

There's no more need to manually loop over turns and players or to detect
whether anyone needs to redeploy their tokens after being attacked. But this
implicit control flow is somewhat confusing.

```python
def on_turn_start(game: Game) -> None:
    player_id = game.player_id
    print(f"Player {player_id} is starting its turn...")
    ai = ais[player_id]
    ai.execute_turn(game)

def on_redeploy(game: Game) -> None:
    player_id = game.player_id
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
# You could also call it from on_turn_start() or execute_turn(),
# but this leads to horrible recursing stack traces.
```

You can find other examples in tests and in pre-0.14.0 `smawg.cli` sources.
