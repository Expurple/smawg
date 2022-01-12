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
    # Do stuff

def on_turn_end(game: Game) -> None:
    # Do stuff

def on_game_end(game: Game) -> None:
    # Do stuff
```


## Example of defining hooks

```python
def on_turn_start(game: Game) -> None:
    player_id = game.current_player_id
    print(f"Player {player_id} is starting its turn...")
    ai = ais[player_id]
    ai.do_its_thing(game)

hooks = {
    "on_turn_start": on_turn_start
}
game = Game(some, other, args, hooks=hooks)
```


You can find another example of hook definition in
[smawg/cli.py](../smawg/cli.py)

Hooks there are only observing, and the majority of the work is still just
imperative method calls.

This situation will probably change in the future.
