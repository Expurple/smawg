# Style

`smawg play` has two output formats, optimized for different use cases:

- `human`. The default style, optimized for manual testing and exploration.
- `machine`. Optimized for machine readability. Its main purpose is to support
    interoperability with clients in other programming languages.

The format is chosen through the `--style` parameter.

## Quick comparison

| Feature                         | `human`                                    | `machine`                          |
| ------------------------------- | ------------------------------------------ | ---------------------------------- |
| Input prompt                    | `'> '`                                     | None                               |
| Status messages                 | Startup, turn change, game end             | None                               |
| `help` command prints           | Help directly                              | JSON with a `"result"` string      |
| Valid `show-...` commands print | Human-readable tables                      | JSON with a `"result"` array       |
| Valid game actions print        | Only dice roll results                     | Always JSON with a `"result"`      |
| Invalid commands print          | Human-readable error with help suggestion  | JSON with detailed `"error"`       |
| Empty commands                  | Do nothing                                 | Print a JSON with `"error"`        |
| Entering the dice value (`-d`)  | On a separate line, after a prompt         | On a separate line, with no prompt |
| Invalid dice values (`-d`)      | Prompt to re-enter                         | Fail the action                    |
| `EOFError`, `KeyboardInterrupt` | Caught, cause to silently exit with code 1 | Not caught, cause a crash          |

## Details for `machine`

The main interaction loop looks like this:

- The user gives a command. The syntax is exactly the same as with `human` style.
- `smawg` prints back a JSON object, containing either `"result"` or `"error"` key.

The only exception is `conquer-dice` command, when `smawg` is run with `-d` flag.
The user must enter the dice value on a separate line right after the command.
`smawg` won't respond with anything before that.

Obviously, `quit` command is also an exception, because it causes `smawg` to
exit, rather than do something and print the result.
