
# exordos_metapaas_s3_buckets_show

Show bucket

## Usage

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 buckets show [OPTIONS] UUID                                                                                                                                                                                                                                                    
                                                                                                                                                                                                                                                                                                           
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
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 buckets show [OPTIONS] UUID                                                                                                                                                                                                                                                    
                                                                                                                                                                                                                                                                                                           
 Show bucket                                                                                                                                                                                                                                                                                               
                                                                                                                                                                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│    --output         -o  [json|html|table|yaml]  the output format, defaults to table                                                                                                                                                                                                                    │
│ *  --instance-uuid      UUID                    [required]                                                                                                                                                                                                                                              │
│    --help                                       Show this message and exit.                                                                                                                                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
