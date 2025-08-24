import configparser
import os


class Configer():
    def __init__(self, filename='config.ini'):
        self.config = configparser.ConfigParser()
        self.filename = filename
        if not os.path.exists(self.filename):
            open(self.filename, 'w').close()
            self.config['Window'] = {'width': 1080, 'height': 720}
            self.config['Path'] = {'dir': ''}
            self.save_config()
        else:
            self.config.read(self.filename)

    def save_config(self):
        with open(self.filename, 'w') as configfile:
            self.config.write(configfile)

configer = Configer()