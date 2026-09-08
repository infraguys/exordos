
# exordos_metapaas_s3_buckets_add

Add a new bucket

## Usage

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 buckets add [OPTIONS]                                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                                                                                           
```

## Options

* `uuid`:
    * Type: uuid
    * Default: `none`
    * Usage: `-u
--uuid`

  UUID of the bucket

* `project_id` (REQUIRED):
    * Type: uuid
    * Default: `sentinel.unset`
    * Usage: `-p
--project-id`

  UUID of the project in which to create the bucket

* `instance_uuid` (REQUIRED):
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `-i
--instance-uuid`

  UUID of the instance to create the bucket in

* `name` (REQUIRED):
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `-n
--name`

  Name of the bucket

* `description`:
    * Type: text
    * Default: `none`
    * Usage: `--description`

  Description of the bucket

* `versioning_enabled`:
    * Type: boolean
    * Default: `none`
    * Usage: `--versioning`

  Keep object versions in the bucket, cannot be changed later

* `object_lock_enabled`:
    * Type: boolean
    * Default: `none`
    * Usage: `--object-lock`

  Enable object lock on the bucket, cannot be changed later

* `public`:
    * Type: boolean
    * Default: `none`
    * Usage: `--public`

  Allow anonymous read access to the bucket

* `quota_bytes`:
    * Type: integer range
    * Default: `none`
    * Usage: `--quota-bytes`

  Size limit of the bucket in bytes, 0 means unlimited

* `default_retention_mode`:
    * Type: choice
    * Default: `none`
    * Usage: `--default-retention-mode`

  Default object lock retention mode

* `default_retention_days`:
    * Type: integer range
    * Default: `none`
    * Usage: `--default-retention-days`

  Default object lock retention period in days

* `help`:
    * Type: boolean
    * Default: `false`
    * Usage: `--help`

  Show this message and exit.

## CLI Help

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 buckets add [OPTIONS]                                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                                                                                           
 Add a new bucket                                                                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│    --uuid                          -u  UUID                                       UUID of the bucket                                                                                                                                                                                                    │
│ *  --project-id                    -p  UUID                                       UUID of the project in which to create the bucket [required]                                                                                                                                                          │
│ *  --instance-uuid                 -i  TEXT                                       UUID of the instance to create the bucket in [required]                                                                                                                                                               │
│ *  --name                          -n  TEXT                                       Name of the bucket [required]                                                                                                                                                                                         │
│    --description                       TEXT                                       Description of the bucket                                                                                                                                                                                             │
│    --versioning/--no-versioning                                                   Keep object versions in the bucket, cannot be changed later                                                                                                                                                           │
│    --object-lock/--no-object-lock                                                 Enable object lock on the bucket, cannot be changed later                                                                                                                                                             │
│    --public/--no-public                                                           Allow anonymous read access to the bucket                                                                                                                                                                             │
│    --quota-bytes                       INTEGER RANGE [0<=x<=9223372036854775807]  Size limit of the bucket in bytes, 0 means unlimited                                                                                                                                                                  │
│    --default-retention-mode            [governance|compliance]                    Default object lock retention mode                                                                                                                                                                                    │
│    --default-retention-days            INTEGER RANGE [1<=x<=365000]               Default object lock retention period in days                                                                                                                                                                          │
│    --help                                                                         Show this message and exit.                                                                                                                                                                                           │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
