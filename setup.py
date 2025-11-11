from setuptools import setup



setup(

    name='appscope',

    version='0.1.0',

    description='A Unified Linux Application Security Console.',

    author='Truman', # Use your name here

    url='https://github.com/truman-dev/appscope', # Use your GitHub link

    scripts=['appscope_gui.py'],

    install_requires=[

        # No Python packages are strictly needed here since Tkinter is a system dependency

    ],

)

