
# exordos_metapaas_s3_instances_add

Add a new instance

## Usage

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 instances add [OPTIONS]                                                                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                                                           
```

## Options

* `uuid`:
    * Type: uuid
    * Default: `none`
    * Usage: `-u
--uuid`

  UUID of the instance

* `project_id` (REQUIRED):
    * Type: uuid
    * Default: `sentinel.unset`
    * Usage: `-p
--project-id`

  UUID of the project in which to deploy the instance

* `name` (REQUIRED):
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `-n
--name`

  Name of the instance

* `description`:
    * Type: text
    * Default: `none`
    * Usage: `--description`

  Description of the instance

* `version` (REQUIRED):
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `-v
--version`

  UUID or name of the s3 version

* `cpu` (REQUIRED):
    * Type: integer range
    * Default: `sentinel.unset`
    * Usage: `--cpu`

  Number of CPU cores per node

* `ram` (REQUIRED):
    * Type: integer range
    * Default: `sentinel.unset`
    * Usage: `--ram`

  RAM per node in MB

* `disk_size` (REQUIRED):
    * Type: integer range
    * Default: `sentinel.unset`
    * Usage: `--disk-size`

  Disk size per node in GB

* `nodes_number`:
    * Type: integer range
    * Default: `1`
    * Usage: `--nodes-number`

  Number of nodes in the cluster

* `help`:
    * Type: boolean
    * Default: `false`
    * Usage: `--help`

  Show this message and exit.

## CLI Help

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 instances add [OPTIONS]                                                                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                                                           
 Add a new instance                                                                                                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│    --uuid          -u  UUID                                UUID of the instance                                                                                                                                                                                                                         │
│ *  --project-id    -p  UUID                                UUID of the project in which to deploy the instance [required]                                                                                                                                                                               │
│ *  --name          -n  TEXT                                Name of the instance [required]                                                                                                                                                                                                              │
│    --description       TEXT                                Description of the instance                                                                                                                                                                                                                  │
│ *  --version       -v  TEXT                                UUID or name of the s3 version [required]                                                                                                                                                                                                    │
│ *  --cpu               INTEGER RANGE [1<=x<=128]           Number of CPU cores per node [required]                                                                                                                                                                                                      │
│ *  --ram               INTEGER RANGE [512<=x<=1073741824]  RAM per node in MB [required]                                                                                                                                                                                                                │
│ *  --disk-size         INTEGER RANGE [8<=x<=1073741824]    Disk size per node in GB [required]                                                                                                                                                                                                          │
│    --nodes-number      INTEGER RANGE [1<=x<=16]            Number of nodes in the cluster [default: 1]                                                                                                                                                                                                  │
│    --help                                                  Show this message and exit.                                                                                                                                                                                                                  │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
