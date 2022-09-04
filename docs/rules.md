# Rules

`smawg` can use custom Python plugins
that introduce new rules and new terrain/race/ability effects.

Let's say, you want to add a debuff ability called Stay-At-Home
that prohibits the player from abandoning regions.

To do that, you need to subclass `smawg.common.AbstractRules`.
Usually, this is done by subclassing `smawg.default_rules.Rules`
and overriding only the methods where you add changes.
In this case, we need to override `check_abandon()`:

```python
from smawg.common import RulesViolation
from smawg.default_rules import Rules as DefaultRules


# This is optional, you can raise `RulesViolation` directly.
# But a separate subclass is easier to catch and test.
class NotStayingAtHome(RulesViolation):
    def __init__(self) -> None:
        msg = "Stay-At-Home races don't like leaving their regions"
        super().__init__(msg)


class CustomRules(DefaultRules):
    def check_abandon(self, region: int) -> None:
        # Check the default rules first.
        super().check_abandon(region)
        if self._game.player.active_ability.name == "Stay-At-Home":
            raise NotStayingAtHome()
```

Then, you need to get `assets` that contain your Stay-At-Home ability
and pass `assets` and `CustomRules` to the `Game` constructor:

```python
from smawg import Game


# Instead of modifying an existing file,
# you can create a new one
# or define `assets` as a dict right here.
with open("smawg/assets/tiny.json") as assets_file:
    assets = json.load(assets_file)
assets["abilities"][0]["name"] = "Stay-At-Home"

game = Game(assets, CustomRules)
```

That's it!
