# Indra v0.1.1

A CLI tool for fetching data from open data sources, to be extended to forecast as well.
Currently, only the fetching data from CDS and ECPDS is implemented.

## Installation

### Using Pip

You can install using pip and github directly:
```bash
pip install git+https://github.com/dsih-artpark/indra
```

This will install from the default branch, i.e. ```production```.

#### Update
```bash
pip install --upgrade git+https://github.com/dsih-artpark/indra
```

## Configuration

The application requires two configuration files:

1. Environment variables file (copy and modify `example.env`):
```bash
cp example.env .env
```

2. A YAML file for application settings (copy and modify `example.yaml`):
```bash
cp example.yaml config.yaml
```

### CDS API Setup

1. Create an account on the [Climate Data Store](https://cds.climate.copernicus.eu/)
2. Accept the Terms of Use
3. Create a `.cdsapirc` file in your home directory with your API key:
```bash
url: https://cds.climate.copernicus.eu/api/v2
key: YOUR-API-KEY
```

## Usage

### Basic Commands

```bash
# Fetch CDS data for current month
indra fetch cds config.yaml

# Fetch CDS data with custom date range (specified in yaml)
indra fetch cds config.yaml --custom-date

# Enable debug mode
indra fetch cds config.yaml --debug

# Set custom log level and file
indra --log-level DEBUG --log-file "custom.log" fetch cds config.yaml
```

### Command Options

#### Global Options
- `--log-level, -l`: Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `--log-file, -f`: Specify custom log file

#### CDS Command Options
- `--current-month/--custom-date, -c/-C`: Use current month or dates from config
- `--debug/--no-debug, -d/-D`: Enable/disable debug mode

## Configuration Files

### YAML Configuration

The YAML configuration file contains settings for:

```yaml
shared_params:
  local_data_dir: "~/.dsih-data/"
  email_recipients:
    "user@example.com": "User Name"
  s3_bucket: 'example-bucket-name'

cds:
  # CDS-specific configuration
  cds_dataset_name: "reanalysis-era5-single-levels"
  bounds_nwse:
    ka: [19,74,11,79]  # Example bounds
  variables:
    "2m_temperature": "2t"
    # ... other variables

ecpds:
  # ECPDS-specific configuration
  url: 'https://data.ecmwf.int/forecasts'
  # ... other settings
```

### Environment Variables

Required environment variables in `.env`:

```env
# CDS API Credentials
CDS_URL=https://cds.climate.copernicus.eu/api/v2
CDS_KEY=YOUR_CDS_API_KEY

# AWS S3 Credentials
AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY
AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_KEY
AWS_DEFAULT_REGION=ap-south-1

# Email Configuration
SMTP_SERVER=smtp.gmail.com
PORT=587
EMAIL=your.email@gmail.com
PASSWORD=your_app_specific_password
```

## Features

- Fetch ERA5 reanalysis data from CDS
- Download ECMWF operational forecasts
- Automatic S3 upload of downloaded data
- Email notifications for job status
- Configurable logging
- Support for multiple regions and variables
- Automatic file cleanup after S3 upload

## Development

### Prerequisites
- Python 3.11+
- AWS credentials ( if using S3. You can use the api and store files in your own server and skip the s3 set up)
- CDS API access

### Setting up Development Environment

Poetry is required for development.

1. Install development dependencies:
```bash
poetry install --with dev
```

2. Install documentation dependencies:
```bash
poetry install --with docs
```

### Documentation

Build the documentation:
```bash
cd docs
make html
```

## License

This project is licensed under the GPL-3.0 License - see the LICENSE file for details.

## Authors

- Sai Sneha <sneha@artpark.in>
- Aishwarya R <aishwarya@artpark.in>
- Akhil Babu <akhil@artpark.in>
