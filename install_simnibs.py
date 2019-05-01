#! /usr/bin/env python
import os
import sys
import tempfile
import subprocess
import argparse
import shutil
import logging
import copy
import re
import requests
# TEMPORARY

from PyQt5 import QtCore, QtWidgets, QtGui

__version__ = '0.1'
GH_RELEASES_URL = 'https://api.github.com/repos/guilhermebs/TestNibs/releases'
HEADERS={}

#logger = logging.getLogger(__name__)
logger = logging.Logger('simnibs_installer', level=logging.INFO)
sh = logging.StreamHandler()
formatter = logging.Formatter('[ %(name)s ]%(levelname)s: %(message)s')
sh.setFormatter(formatter)
logger.addHandler(sh)
logger.setLevel(logging.INFO)

def log_excep(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Uncaught exception",
                 exc_info=(exc_type, exc_value, exc_traceback))
    logger.debug("Traceback",
                 exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = log_excep

def _get_versions(preselease=False):
    ''' Get avaliable SimNIBS version '''
    response = requests.get(GH_RELEASES_URL, headers=HEADERS)
    # Raise an exception if the API call fails.
    response.raise_for_status()
    data = response.json()
    versions = {}
    for i, d in enumerate(data):
        if d['tag_name'][0] == 'v' and not (d['prerelease'] or preselease):
            versions[d['tag_name'][1:]] = i
    return versions


def _get_current_version(target_dir):
    ''' Gets the current SimNIBS version by looking at the simnibs executable'''
    res = subprocess.run(
        [os.path.join(target_dir, 'bin', 'simnibs'), '--version'],
        capture_output=True)
    try:
        res.check_returncode()
    except subprocess.CalledProcessError():
        return None
    return res.stdout.decode().rstrip('\n')

def _download_env(version, target_dir):
    ''' Looks for a given environment file os SimNIBS in the GitHub Releases
    '''
    response = requests.get(GH_RELEASES_URL, headers=HEADERS)
    # Raise an exception if the API call fails.
    response.raise_for_status()
    data = response.json()
    avaliable_versions = _get_versions()
    try:
        release_data = data[avaliable_versions[version]]
    except KeyError:
        ver_string = '\n'.join(avaliable_versions.keys())
        raise ValueError(
            f'\nCould not find SimNIBS version: {version}\n'
            f'Avaliable versions are:\n{ver_string}')

    # Download the environment file
    env_file = _env_file()
    dl_header = copy.deepcopy(HEADERS)
    dl_header['Accept'] = 'application/octet-stream'
    for asset in release_data['assets']:
        if asset['name'] == env_file:
            logger.info(
                f"Downloading the environment file for version: "
                f"{release_data['tag_name'][1:]}")
            r = requests.get(
                f'{GH_RELEASES_URL}/assets/{asset["id"]}',
                headers=dl_header, allow_redirects=True)
            r.raise_for_status()
            open(os.path.join(target_dir, env_file), 'wb').write(r.content)
            logger.info('Finished downloading the environment file')

    return release_data['html_url']

def _env_file():
    if sys.platform == 'win32':
        return 'environment_win.yml'
    else: 
        return 'environment_unix.yml'


def _download_and_install_miniconda(miniconda_dir):
    # Download Miniconda installer
    if sys.platform == 'linux':
        url = "https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    elif sys.platform == 'darwin':
        url = "https://repo.continuum.io/miniconda/Miniconda3-latest-MacOSX-x86_64.sh"
    elif sys.platform == 'win32':
        url = "https://repo.continuum.io/miniconda/Miniconda3-latest-Windows-x86_64.exe"
    else:
        raise OSError('OS not supported')
    logger.info('Downloading the Miniconda installer')
    r = requests.get(url, allow_redirects=True)
    r.raise_for_status()
    if sys.platform == 'win32':
        miniconda_installer_path = 'miniconda_installer.exe'
        open(miniconda_installer_path, 'wb').write(r.content)
        logger.info('Finished downloading the Miniconda installer')
        logger.info('Installing Miniconda, this might take some time')
        run_command(
            [miniconda_installer_path, '/InstallationType=JustMe',
            '/RegisterPython=0', '/AddToPath=0', '/S', f'/D={miniconda_dir}'])
        os.remove(miniconda_installer_path)
    else:
        miniconda_installer_path = 'miniconda_installer.sh'
        open(miniconda_installer_path, 'wb').write(r.content)
        logger.info('Finished downloading the Miniconda installer')
        # Run the instaler
        run_command(
            ['bash', miniconda_installer_path,
             '-b', '-f', '-p', miniconda_dir])
        os.remove(miniconda_installer_path)

def _install_env_and_simnibs(version_url, conda_executable, target_dir):
    ''' Install the environment and SimNIBS

    Parameters
    -----------
    version_url: str
        Url to the address with the .whl files
    conda_executable: str
        Path to the conda executable
    '''
    logger.info('Installing the environment and SimNIBS')
    logger.debug(f'Download URL: {version_url}')
    logger.debug(f'Conda executable: {conda_executable}')
    activate_executable = os.path.join(os.path.dirname(conda_executable), 'activate')
    env_file = os.path.join(target_dir, _env_file())
    # We write a shell script and execute it due to the activate calls
    if sys.platform == 'win32':
        with tempfile.NamedTemporaryFile(delete=False, suffix='.cmd') as f:
            f.write((
                f'set PYTHONUNBUFFERED=1\n'
                f'call {activate_executable} base\n'
                f'conda env update -f {env_file}\n'
                f'call conda activate simnibs_env\n'
                f'pip install --upgrade -f {version_url} simnibs').encode())
            fn_tmp = f.name
        run_command(['cmd', '/Q', '/C', fn_tmp])
        os.remove(fn_tmp)
    else:
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write((
                f'export PYTHONUNBUFFERED=1\n'
                f'source {activate_executable} base\n'
                f'conda env update -f {env_file}\n'
                f'conda activate simnibs_env\n'
                f'pip install --upgrade -f {version_url} simnibs').encode())
            fn_tmp = f.name
        run_command(['bash', '-e', fn_tmp])
        os.remove(fn_tmp)


def _run_postinstall(conda_executable, target_dir):
    ''' Run SimNIBS postinstall '''
    logger.info('Running SimNIBS postinstall script')
    activate_executable = os.path.join(os.path.dirname(conda_executable), 'activate')
    logger.debug(f'activate executable: {activate_executable}')
    logger.debug(f'target dir: {target_dir}') 
    # We write a shell script and execute it due to the activate calls
    if sys.platform == 'win32':
        with tempfile.NamedTemporaryFile(delete=False, suffix='.cmd') as f:
            f.write((
                f'call {activate_executable} simnibs_env\n'
                f'simnibs_postinstall -d {target_dir}').encode())
            fn_tmp = f.name
        run_command(['cmd', '/Q', '/C', fn_tmp])
        os.remove(fn_tmp)
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write((
            f'source {activate_executable} simnibs_env\n'
            f'simnibs_postinstall -d {target_dir}').encode())
        fn_tmp = f.name
    run_command(['bash', '-e', fn_tmp])
    os.remove(fn_tmp)


def run_command(command, log_level=logging.INFO):
    """ Run a command and logs it
    """
    command_str = ' '.join(command)
    logger.log(log_level, f'Execute: {command_str}')
    if sys.platform == 'win32':
        command = command_str
        shell = True
    else:
        shell = False
    command_line_process = subprocess.Popen(
        command, shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL)
    while command_line_process.returncode is None:
        command_line_process.poll()
        for line in command_line_process.stdout:
            line = line.decode().rstrip('\n')
            if line != '':
                logger.log(log_level, line)

    _, stderr = command_line_process.communicate()
    stderr = stderr.decode()
    if stderr != '':
        logger.error('\n' + stderr)
    if command_line_process.returncode == 0:
        logger.debug('Execution finished')

    else:
        raise OSError(f'Error executing command: {command_str}')



def run_install(target_dir, simnibs_version):
    ''' Main function for installation
    
    Parameters
    --------------
    target_dir: str
        Directory where SimNIBS will be installed

    '''
    # Make the install directory
    if not os.path.isdir(target_dir):
        os.makedirs(target_dir)

    # Add a logger
    fh = logging.FileHandler(os.path.join(target_dir, 'simnibs_install_log.txt'), mode='w')
    formatter = logging.Formatter(
        '[ %(name)s - %(asctime)s ]%(levelname)s: %(message)s')
    fh.setFormatter(formatter)
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)

    # Check the currently avaliable versisons
    avaliable_versions = _get_versions()
    if simnibs_version == 'latest':
        requested_version = list(avaliable_versions.keys())[0]
    else:
        requested_version = simnibs_version
    try:
        requested_idx = avaliable_versions[requested_version]
    except KeyError:
        ver_string = '\n'.join(avaliable_versions.keys())
        raise ValueError(
            f'Could not find requested SimNIBS version: {simnibs_version}'
            f'\nAvaliable versions are:\n{ver_string}')

    # Check the current installed version
    if os.path.isfile(os.path.join(target_dir, 'bin', 'simnibs')):
        logger.info('SimNIBS installation detected! Updating it')
        curr_version = _get_current_version(target_dir)
        try:
            curr_idx = avaliable_versions[curr_version]
        except KeyError:
            curr_idx = len(avaliable_versions) + 1
            logger.error('Could not determine the current SimNIBS version')
            logger.info('Updating to the latest version')
        else:
            if requested_idx > curr_idx:
                raise ValueError(
                    "Can't downgrade SimNIBS!\n"
                    f"current version: {curr_version}\n"
                    f"requested version: {requested_version}\n")
                return
            elif curr_idx == requested_idx:
                logger.info('SimNIBS is already in the requested version')
                return
            else:
                logger.info(f'Updating SimNIBS {curr_version} -> {requested_version}')
    else:
        logger.debug('did not find any SimNIBS install in the target folder')
        logger.info(f'Installing SimNIBS {requested_version}')


    logger.info(f'Installing SimNBIS to: {target_dir}')
    # Check is Miniconda is alteady present
    miniconda_dir = os.path.join(target_dir, 'miniconda3')
    if sys.platform == 'win32':
        conda_executable = os.path.join(miniconda_dir, 'Scripts', 'conda.exe')
    else:
        conda_executable = os.path.join(miniconda_dir, 'bin', 'conda')
    print(conda_executable)
    if os.path.isfile(conda_executable):
        logger.info('Miniconda installation detected, skipping install step')
    else:
        _download_and_install_miniconda(miniconda_dir)
    # Install SimNIBS
    url = _download_env(requested_version, target_dir)
    _install_env_and_simnibs(url, conda_executable, target_dir)
    _run_postinstall(conda_executable, target_dir)
    shutil.copy(__file__, target_dir)
    logger.info('SimNIBS sucessefully installed')


class InstallGUI(QtWidgets.QWizard):
    ''' Installation wizard '''
    def __init__(self,
                 target_dir,
                 simnibs_version='latest'):
        super().__init__()
        self.target_dir = target_dir
        self.simnibs_version = simnibs_version

        # Button layout without the back button
        buttons_layout = []
        buttons_layout.append(QtWidgets.QWizard.Stretch )
        buttons_layout.append(QtWidgets.QWizard.NextButton )
        buttons_layout.append(QtWidgets.QWizard.FinishButton)
        buttons_layout.append(QtWidgets.QWizard.CancelButton )
        self.setButtonLayout(buttons_layout)

        # Add the pages
        self.addPage(self.options_page())
        self.addPage(self.install_page())
        self.setWindowTitle('SimNIBS Installer')
        self.setWindowIcon(QtGui.QIcon('gui_icon.gif'))


    def options_page(self):
        ''' First page, where options are set '''
        options_page = QtWidgets.QWizardPage()
        options_page.setTitle('Installation Options')
        options_page.setSubTitle(
            'The installer will donwload and install SimNIBS 3 and its requiremets.\n'
            'SimNIBS requires about 3 GB of space')
        layout = QtWidgets.QGridLayout()

        layout.addWidget(QtWidgets.QLabel('Install Directory:'), 0, 0)
        self.target_dir_line_edit = QtWidgets.QLineEdit()
        if self.target_dir is not None:
            self.target_dir_line_edit.setText(self.target_dir)
            self.target_dir_line_edit.textChanged.connect(self.set_target_dir)
        layout.addWidget(self.target_dir_line_edit, 0, 1)

        select_file = QtWidgets.QPushButton('&Browse')
        select_file.clicked.connect(self.select_dir)
        layout.addWidget(select_file, 0, 2)


        layout.addWidget(QtWidgets.QLabel('Version to install:'), 1, 0)
        version_box = QtWidgets.QComboBox()
        version_box.activated.connect(self.set_simnibs_version)
        self.avaliable_versions = _get_versions()
        latest_version = list(self.avaliable_versions.keys())[0]
        if self.simnibs_version == 'latest':
           selected_version = latest_version
        else:
           try:
                self.avaliable_versions[self.simnibs_version]
           except KeyError:
                logger.warn(
                    f'Could not find requested SimNIBS version: {self.simnibs_version}')
                selected_version = latest_version

        version_box.addItems(list(self.avaliable_versions.keys()))
        version_box.setCurrentIndex(list(self.avaliable_versions.keys()).index(selected_version))
        layout.addWidget(version_box, 1, 1)

        license_label = QtWidgets.QLabel(
            'I Agree to the <a href="http://www.simnibs.org/license"> SimNIBS </a>'
            ' and <a href="https://docs.continuum.io/anaconda/eula"> Miniconda </a> licenses')
        license_label.setOpenExternalLinks(True)
        layout.addWidget(license_label, 2, 1)
        license = QtWidgets.QCheckBox()
        layout.addWidget(license, 2, 2)

        options_page.registerField("license*", license)

        options_page.setLayout(layout)
        return options_page


    def set_target_dir(self, new_value):
        self.target_dir = new_value

    def select_dir(self):
        self.target_dir = str(QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory"))
        if self.target_dir:
            self.target_dir_line_edit.setText(self.target_dir)

    def set_simnibs_version(self, index):
        self.simnibs_version = list(self.avaliable_versions.keys())[index]

    def install_page(self):
        ''' Second page, with the install output '''
        install_page = QtWidgets.QWizardPage()
        layout = QtWidgets.QGridLayout()

        text_box = QtWidgets.QTextEdit()
        text_box.setReadOnly(True)
        text_box.setAcceptRichText(True)


        layout.addWidget(text_box)
        install_page.setLayout(layout)


        self.install_thread = None
        def start_thread():
            ''' Starts the install procedure '''
            self.install_thread = InstallerThread(
                self, self.target_dir, self.simnibs_version)
            self.install_thread.start()
            self.install_thread.out_signal.connect(text_box.append)
            self.install_thread.finished.connect(install_page.completeChanged.emit)

        def install_finished():
            ''' Changes the status '''
            if self.install_thread is None:
                return False
            else:
                return self.install_thread.isFinished()

        install_page.initializePage = start_thread
        install_page.isComplete = install_finished

        return install_page


@QtCore.pyqtSlot(str)
class InstallerThread(QtCore.QThread):
    ''' Thread to install SimNIBS '''
    out_signal = QtCore.pyqtSignal(str)

    def __init__(self, parent, target_dir, simnibs_version):
        QtCore.QThread.__init__(self)
        self.parent = parent
        self.target_dir = target_dir
        self.simnibs_version = simnibs_version

    def run(self):
        ''' Write log to box '''
        class WriteToBoxHandler(logging.StreamHandler):
            def __init__(self, out_signal):
                super().__init__()
                self.out_signal = out_signal

            def emit(self, record):
                msg = self.format(record)
                self.out_signal.emit(msg)

        w2b_handler = WriteToBoxHandler(self.out_signal)
        w2b_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logger.addHandler(w2b_handler)
        try:
            run_install(self.target_dir, self.simnibs_version)
        except Exception as e:
            # The message box bellow is causing segmentation faults
            #QtWidgets.QMessageBox.critical(self.parent, 'Error', str(e))
            logger.critical(str(e))
            raise e
        finally:
            logger.removeHandler(w2b_handler)

def start_gui(target_dir, simnibs_version):
    app = QtWidgets.QApplication(sys.argv)
    ex = InstallGUI(target_dir, simnibs_version)
    ex.show()
    response = app.exec_()
    sys.exit(response)


def _get_default_dir():
    if os.path.isfile(os.path.join('bin', 'simnibs')):
        return os.path.abspath('.')

    if sys.platform == 'win32':
        return os.path.join(os.environ['LOCALAPPDATA'], 'SimNIBS')
    elif sys.platform == 'linux':
       return os.path.join(os.environ['HOME'], 'SimNIBS')


def main():
    parser = argparse.ArgumentParser(prog="install_simnibs",
                                     description="Updates SimNIBS to a given version")
    parser.add_argument('-s', '--silent', action='store_true',
                        help="Run installation in silend mode (no GUI)")
    parser.add_argument('-d', '--target_dir', required=False,
                        help="Directory where to install SimNIBS",
                        default=_get_default_dir())
    parser.add_argument("-v", '--simnibs_version', required=False,
                        default="latest",
                        help="Version of SimNIBS to install."
                             " Default: latest version")
    parser.add_argument('--version', action='version', version=__version__)
    args = parser.parse_args(sys.argv[1:])
    if args.silent:
        run_install(args.target_dir, args.simnibs_version)
    else:
        start_gui(args.target_dir, args.simnibs_version)

# First scans the current directory for a SimNIBS install
# Then proposes a new directory

if __name__ == '__main__':
    main()
