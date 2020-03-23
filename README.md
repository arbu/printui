## Print UI

This is a web service to print labels on Brother QL label printers.

This is a fork of [brother_ql_web](https://github.com/pklaus/brother_ql_web).

### Dependencies

Print UI is written for python 3. It requires the following python libraries:

```
bottle
jinja2
brother_ql
fontconfig
```

[fontconfig](https://github.com/ldo/python_fontconfig) is currently not available on pypi but can be installed with `pip install 'git+https://github.com/ldo/python_fontconfig.git@v0.7#egg=fontconfig'`. The *fontconfig* python library also needs the *libfontconfig* installed on your system.

### Usage

Running `python setup.py install` will install the command `printui`. Executing `printui` will try to find a device automatically and start a webserver on port 8080. A configuration file can be specified with `-d <config>`.

### License

This software is published under the terms of the GPLv3, see the LICENSE file in the repository.

Parts of this package are redistributed software products from 3rd parties. They are subject to different licenses:

  * [Bootswatch](https://bootswatch.com/), MIT License

  * [jQuery](https://jquery.com/), MIT License

  * [Popper](https://popper.js.org/), MIT License

  * [Lato](http://www.latofonts.com/lato-free-fonts/), SIL OFL 1.1

  * [Font Awesome](https://fontawesome.com/), CC BY 4.0/SIL OFL 1.1/MIT License
