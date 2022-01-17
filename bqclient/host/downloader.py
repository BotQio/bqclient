import os
from typing import Optional, Union

from appdirs import AppDirs
import requests

from bqclient.host.api.rest import RestApi
from bqclient.host.models import File


class Downloader(object):
    def __init__(self,
                 api: RestApi,
                 app_dirs: AppDirs):
        self._api = api
        self.app_dirs = app_dirs

    def download(self, url: Union[str, File], name: Optional[str] = None):
        downloads = os.path.join(self.app_dirs.user_data_dir, "downloads")
        os.makedirs(downloads, exist_ok=True)

        if isinstance(url, File):
            name = url.name
            url = url.download_url

        if name is None:
            name = "file.gcode"

        file_name = os.path.join(downloads, name)

        with self._api.get(url) as http_request:
            print(http_request.status_code)
            with open(file_name, 'wb') as fh:
                fh.write(http_request.content)

        return file_name
