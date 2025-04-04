import logging
import os

import boto3

logger = logging.getLogger(__name__)

def upload_data_to_s3(*,
                      upload_dir: str,
                      Bucket: str,
                      Prefix: str,
                      extension: str,
                      raise_error: bool = False
                      ):
    """Upload data from the local directory to an S3 bucket and delete files from the local directory.

    This function uploads data from a local directory to an S3 bucket and deletes those files from the local directory.

    :param str upload_dir:
        Directory containing the data to upload.

    :param str Bucket:
        Name of the S3 bucket to upload the data to.

    :param str Prefix:
        Prefix to use for the S3 object keys.

    :param str extension:
        File extension of the data files.

    :param bool raise_error:
        Whether to raise an error if the data is not uploaded successfully.

        **Default**: ``False``

    :returns:
        True if the data was uploaded successfully, False otherwise.

    :raises Exception:
        If there is an issue with the S3 upload.

    **Example:**

    ```python
    upload_data_to_s3(
        upload_dir="./data",
        Bucket="my-s3-bucket",
        Prefix="climate-data",
        extension="nc"
    )
    ```
    """
    logger.info("Starting upload of data to S3 bucket")
    logger.debug(f"Upload directory: {upload_dir}")
    logger.debug(f"Bucket name: {Bucket}")
    logger.debug(f"Prefix: {Prefix}")

    client = boto3.client('s3')
    logger.info("S3 client initialized")

    no_files = len([file for file in os.listdir(upload_dir) if file.endswith(extension)])
    logger.info(f"Number of files to upload: {no_files}")
    failed_uploads = 0
    total_uploads = 0
    for file in os.listdir(upload_dir):
        if file.endswith(extension):
            total_uploads += 1
            logger.info(f"Uploading {file} to S3 bucket")
            try:
                Key = f"{Prefix}/{file}"
                client.upload_file(Filename=os.path.join(upload_dir, file),
                                  Bucket=Bucket, Key=Key)
                logger.info(f"Uploaded {file} to S3 bucket")
                os.remove(os.path.join(upload_dir, file))
                logger.info(f"Deleted {file} from local directory")
            except Exception as e:
                logger.error(f"Failed to upload {file} to S3 bucket: {e!s}")
                if raise_error:
                    raise
                else:
                    logger.warning(f"Failed to upload {file} to S3 bucket: {e!s}")
                    failed_uploads += 1
                    continue

    if failed_uploads > 0:
        logger.warning(f"Failed to upload {failed_uploads}/{total_uploads} files with ext {extension} Bucket: {Bucket}, Prefix: {Prefix}")
        return failed_uploads
    else:
        logger.info(f"Successfully uploaded all {total_uploads} files with ext {extension} Bucket: {Bucket} Prefix: {Prefix}")
        return failed_uploads
