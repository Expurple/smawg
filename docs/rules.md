# Rules

`smawg` can use custom Python plugins
that introduce new rules and new terrain/race/ability effects.

## Example

Let's say, you want to add a debuff ability called Stay-At-Home
that prohibits the player from abandoning regions.

### With `smawg` as a library

You need to implement `smawg.AbstractRules`.
Usually, this is done by subclassing `smawg.default_rules.Rules`
and overriding only the methods where you add changes.
In this case, we need to override `check_abandon()`:

```python
from typing import Iterator

from smawg import RulesViolation
from smawg.default_rules import Rules as DefaultRules


# This is optional, you can raise `RulesViolation` directly.
# But a separate subclass is easier to catch and test.
class NotStayingAtHome(RulesViolation):
    def __init__(self) -> None:
        msg = "Stay-At-Home races don't like leaving their regions"
        super().__init__(msg)


class CustomRules(DefaultRules):
    def check_abandon(self, region: int
                      ) -> Iterator[ValueError | RulesViolation]:
        # Check the default rules first.
        yield from super().check_abandon(region)
        players_ability = self._game.player.active_ability
        # Type narrowing for mypy.
        assert players_ability is not None, "should be already checked"
        if players_ability.name == "Stay-At-Home":
            yield NotStayingAtHome()
```

Then, you need to get `assets` that contain your Stay-At-Home ability
and pass `assets` and `CustomRules` to the `Game` constructor:

```python
from smawg import Game


# Instead of modifying an existing file, you can create a new one
# or define `assets` right here as dict or as Assets object.
with open("smawg/assets/tiny.json") as assets_file:
    assets = json.load(assets_file)
assets["abilities"][0]["name"] = "Stay-At-Home"

game = Game(assets, CustomRules)
```

That's it!

### With `smawg.cli`

The first step is mostly the same.
You need to define your `smawg.AbstractRules` sublass in a Python file.
The difference is that the subclass must be named `Rules`
(not `CustomRules` or anyting else).
This is a convention so that the loader can find it.

Then, again, you need to create an assets file that contains this ability.

Then, pass the rules plugin and the assets file to `smawg.cli`:

```bash
python3 -m smawg.cli --rules=custom_rules.py custom_assets.json
```
