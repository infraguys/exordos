
# exordos_metapaas_s3_user-policies_show

Show policy attachment

## Usage

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 user-policies show [OPTIONS] UUID                                                                                                                                                                                                                                              
                                                                                                                                                                                                                                                                                                           
```

## Options

* `uuid` (REQUIRED):
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `uuid`

* `output`:
    * Type: choice
    * Default: `table`
    * Usage: `--output
-o`

  the output format, defaults to table

* `user_uuid` (REQUIRED):
    * Type: uuid
    * Default: `sentinel.unset`
    * Usage: `--user-uuid`

* `instance_uuid` (REQUIRED):
    * Type: uuid
    * Default: `sentinel.unset`
    * Usage: `--instance-uuid`

* `help`:
    * Type: boolean
    * Default: `false`
    * Usage: `--help`

  Show this message and exit.

## CLI Help

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 user-policies show [OPTIONS] UUID                                                                                                                                                                                                                                              
                                                                                                                                                                                                                                                                                                           
 Show policy attachment                                                                                                                                                                                                                                                                                    
                                                                                                                                                                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│    --output         -o  [json|html|table|yaml]  the output format, defaults to table                                                                                                                                                                                                                    │
│ *  --user-uuid          UUID                    [required]                                                                                                                                                                                                                                              │
│ *  --instance-uuid      UUID                    [required]                                                                                                                                                                                                                                              │
│    --help                                       Show this message and exit.                                                                                                                                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
