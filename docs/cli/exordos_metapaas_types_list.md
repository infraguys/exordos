
# exordos_metapaas_types_list

List types

## Usage

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas types list [OPTIONS]                                                                                                                                                                                                                                                              
                                                                                                                                                                                                                                                                                                           
```

## Options

* `filters`:
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `-f
--filters`

  Additional filters to pass to the api. The format is 'key=value'. For example: --f parent=11111111-1111-1111-1111-11111111111 --filters status=NEW

* `fields`:
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `--fields`

  fields to show, defaults to all, for example: --fields name --fields status

* `output`:
    * Type: choice
    * Default: `table`
    * Usage: `--output
-o`

  the output format, defaults to table

* `watch`:
    * Type: boolean
    * Default: `false`
    * Usage: `-w
--watch`

  Watch the list of types

* `interval`:
    * Type: float range
    * Default: `0.5`
    * Usage: `--interval`

  Refresh interval in seconds.

* `help`:
    * Type: boolean
    * Default: `false`
    * Usage: `--help`

  Show this message and exit.

## CLI Help

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas types list [OPTIONS]                                                                                                                                                                                                                                                              
                                                                                                                                                                                                                                                                                                           
 List types                                                                                                                                                                                                                                                                                                
                                                                                                                                                                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --filters   -f  TEXT                    Additional filters to pass to the api. The format is 'key=value'. For example: --f parent=11111111-1111-1111-1111-11111111111 --filters status=NEW                                                                                                              │
│ --fields        TEXT                    fields to show, defaults to all, for example: --fields name --fields status                                                                                                                                                                                     │
│ --output    -o  [json|html|table|yaml]  the output format, defaults to table                                                                                                                                                                                                                            │
│ --watch     -w                          Watch the list of types                                                                                                                                                                                                                                         │
│ --interval      FLOAT RANGE [x>=0.1]    Refresh interval in seconds.                                                                                                                                                                                                                                    │
│ --help                                  Show this message and exit.                                                                                                                                                                                                                                     │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
