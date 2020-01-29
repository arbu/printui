from setuptools import setup

with open("README.md", "r") as fh:
    README = fh.read()

setup(
        name='printui',
        version='0.1',
        description='Webinterface to talk to Brother QL label printers. Fork of brother_ql_web',
        long_description=README,
        author='Philipp Klaus, Aaron Bulmahn',
        author_email='arbudev@gmail.com',
        url='https://github.com/arbu/printui',
        license='GPL-3.0-or-later',
        packages=['printui'],
        package_data={'printui': [
            'static/*/*',
            'views/*',
            ]},
        data_files=[('', ['printui.conf.example'])],
        zip_safe=True,
        entry_points={
            'console_scripts': [
                'printui = printui:main',
                ],
            },
        platforms='any',
        install_requires=[
            'setuptools',
            'bottle',
            'jinja2',
            'Pillow',
            'brother_ql',
            'fontconfig',
            ],
        )
