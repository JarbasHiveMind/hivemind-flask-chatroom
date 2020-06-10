from setuptools import setup

setup(
    name='HiveMind-chatroom',
    version='0.0.1',
    packages=['hivemind_chatroom'],
    url='https://github.com/OpenJarbas/HiveMind-chatroom',
    license='MIT',
    author='jarbasAI',
    author_email='jarbasai@mailfence.com',
    description='Mycroft Chatroom',
    install_requires=["jarbas_hive_mind>=0.10.3", "flask"],
    entry_points={
        'console_scripts': [
            'HiveMind-chatroom=hivemind_chatroom.__main__:main'
        ]
    }
)
