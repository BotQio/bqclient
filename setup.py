import re

from setuptools import setup, find_packages


def get_version():
    version_file = "bqclient/_version.py"
    line = open(version_file, "rt").read()
    version_regex = r"^__version__\s*=\s*['\"]([^'\"]*)['\"]"

    match_object = re.search(version_regex, line, re.MULTILINE)

    if match_object:
        return match_object.group(1)
    else:
        raise RuntimeError("Unable to find version string in %s." % version_file)


try:
    from Cython.Build import cythonize
    extensions = cythonize("bqclient/host/drivers/printrun/gcoder_line.pyx")
    from Cython.Distutils import build_ext
except ImportError as e:
    print("WARNING: Failed to cythonize: %s" % e)
    # Debug helper: uncomment these:
    # import traceback
    # traceback.print_exc()
    extensions = []
    build_ext = None


setup(name="bqclient",
      author="Justin Nesselrotte",
      author_email="admin@jnesselr.org",
      description="BotQio's client bqclient",
      version=get_version(),
      url="http://github.com/BotQio/bqclient/",
      packages=find_packages(),
      ext_modules=extensions,
      entry_points={
          "console_scripts": [
              "bqclient = bqclient.__main__:main"
          ]
      },
      setup_requires=[
          "Cython",
          "pytest-runner"
      ],
      install_requires=[
          'appdirs',
          'click',
          'deepdiff',
          'faker',
          'requests',
          'pyserial',
          'pysherplus',
          'sentry-sdk',
          'zeroconf'
      ],
      tests_require=[
          "pytest",
      ],
      )
