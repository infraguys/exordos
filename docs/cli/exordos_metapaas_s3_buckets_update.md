
# exordos_metapaas_s3_buckets_update

Update bucket

## Usage

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 buckets update [OPTIONS] UUID                                                                                                                                                                                                                                                  
                                                                                                                                                                                                                                                                                                           
```

## Options

* `uuid` (REQUIRED):
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `uuid`

* `instance_uuid` (REQUIRED):
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `-i
--instance-uuid`

  UUID of the instance the bucket belongs to

* `description`:
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `--description`

  Description of the bucket

* `public`:
    * Type: boolean
    * Default: `none`
    * Usage: `--public`

  Allow anonymous read access to the bucket

* `quota_bytes`:
    * Type: integer range
    * Default: `sentinel.unset`
    * Usage: `--quota-bytes`

  Size limit of the bucket in bytes, 0 means unlimited

* `default_retention_mode`:
    * Type: choice
    * Default: `sentinel.unset`
    * Usage: `--default-retention-mode`

  Default object lock retention mode

* `default_retention_days`:
    * Type: integer range
    * Default: `sentinel.unset`
    * Usage: `--default-retention-days`

  Default object lock retention period in days

* `help`:
    * Type: boolean
    * Default: `false`
    * Usage: `--help`

  Show this message and exit.

## CLI Help

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 buckets update [OPTIONS] UUID                                                                                                                                                                                                                                                  
                                                                                                                                                                                                                                                                                                           
 Update bucket                                                                                                                                                                                                                                                                                             
                                                                                                                                                                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *  --instance-uuid           -i  TEXT                                       UUID of the instance the bucket belongs to [required]                                                                                                                                                                       │
│    --description                 TEXT                                       Description of the bucket                                                                                                                                                                                                   │
│    --public/--no-public                                                     Allow anonymous read access to the bucket                                                                                                                                                                                   │
│    --quota-bytes                 INTEGER RANGE [0<=x<=9223372036854775807]  Size limit of the bucket in bytes, 0 means unlimited                                                                                                                                                                        │
│    --default-retention-mode      [governance|compliance]                    Default object lock retention mode                                                                                                                                                                                          │
│    --default-retention-days      INTEGER RANGE [1<=x<=365000]               Default object lock retention period in days                                                                                                                                                                                │
│    --help                                                                   Show this message and exit.                                                                                                                                                                                                 │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
