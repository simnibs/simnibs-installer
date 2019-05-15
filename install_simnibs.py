#! /usr/bin/env python

import os
import sys
import subprocess
import argparse
import shutil
import logging
import re
import zipfile

import requests
from PyQt5 import QtCore, QtWidgets, QtGui

__version__ = '1.0'
GH_RELEASES_URL = 'https://api.github.com/repos/simnibs/simnibs/releases'

ENV=None
if getattr( sys, 'frozen', False ):
    FILENAME = sys.executable
    # THIS LINES ARE KEY TO MAKE THE PYINSTALLER-FROZEN APP WORK ON WINDOWS
    # WE NEED TO DISABLE THE SETDLLDIRECTORYA CALL OR IT WILL AFECT ALL CHILD PROCESSES
    # https://github.com/pyinstaller/pyinstaller/issues/3795
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetDllDirectoryA(None)

    # Restore the original environment (Linux)
    # from https://pyinstaller.readthedocs.io/en/v3.3.1/runtime-information.html#ld-library-path-libpath-considerations
    if sys.platform == 'linux':
        ENV = dict(os.environ)  # make a copy of the environment
        lp_key = 'LD_LIBRARY_PATH'  # for Linux and *BSD.
        lp_orig = ENV.get(lp_key + '_ORIG')  # pyinstaller >= 20160820 has this
        if lp_orig is not None:
            ENV[lp_key] = lp_orig  # restore the original, unmodified value
        else:
            ENV.pop(lp_key, None)  # last resort: remove the env var
else:
    FILENAME = __file__


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

def _get_versions(pre_release=False):
    ''' Get avaliable SimNIBS version '''
    response = requests.get(GH_RELEASES_URL)
    # Raise an exception if the API call fails.
    response.raise_for_status()
    data = response.json()
    versions = {}
    #breakpoint()
    for i, d in enumerate(data):
        if d['tag_name'][0] == 'v':
            if not d['prerelease']:
                versions[d['tag_name'][1:]] = i
            if d['prerelease'] and pre_release:
                versions[d['tag_name'][1:]] = i

    return versions

def _simnibs_exe(prefix):
    if sys.platform == 'win32':
        return os.path.abspath(os.path.join(prefix, 'bin', 'simnibs.cmd'))
    else:
        return os.path.abspath(os.path.join(prefix, 'bin', 'simnibs'))

def _get_current_version(prefix):
    ''' Gets the current SimNIBS version by looking at the simnibs executable'''
    try:
        res = subprocess.check_output(
            f'{_simnibs_exe(prefix)} --version',
            shell=True,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL)
    except subprocess.CalledProcessError():
        return None
    return res.decode().rstrip('\n').rstrip('\r')

def _download_env_docs(version, prefix, pre_release):
    ''' Looks for a given environment file os SimNIBS in the GitHub Releases
    '''
    response = requests.get(GH_RELEASES_URL)
    # Raise an exception if the API call fails.
    response.raise_for_status()
    data = response.json()
    avaliable_versions = _get_versions(pre_release)
    try:
        release_data = data[avaliable_versions[version]]
    except KeyError:
        ver_string = '\n'.join(avaliable_versions.keys())
        raise ValueError(
            f'\nCould not find SimNIBS version: {version}\n'
            f'Avaliable versions are:\n{ver_string}')

    # Download the environment file
    env_file = _env_file()
    dl_header = {'Accept': 'application/octet-stream'}
    for asset in release_data['assets']:
        if asset['name'] == env_file:
            logger.info(
                f"Downloading the environment file for version: "
                f"{release_data['tag_name'][1:]}")
            r = requests.get(
                f'{GH_RELEASES_URL}/assets/{asset["id"]}',
                headers=dl_header, allow_redirects=True)
            r.raise_for_status()
            with open(os.path.join(prefix, env_file), 'wb') as f:
                f.write(r.content)
            logger.info('Finished downloading the environment file')
        if asset['name'] == 'documentation.zip':
            logger.info("Downloading the documentation")
            r = requests.get(
                f'{GH_RELEASES_URL}/assets/{asset["id"]}',
                headers=dl_header, allow_redirects=True)
            r.raise_for_status()
            fn_zip = os.path.join(prefix, 'documentation.zip')
            open(fn_zip, 'wb').write(r.content)
            logger.info('Finished downloading the documentation')
            logger.info('Extracting the documentation')
            if os.path.isdir(os.path.join(prefix, 'documentation')):
                shutil.rmtree(os.path.join(prefix, 'documentation'))
            with zipfile.ZipFile(fn_zip) as z:
                z.extractall(os.path.join(prefix, 'documentation'))
            os.remove(fn_zip)
    return release_data['html_url']

def _env_file():
    if sys.platform == 'win32':
        return 'environment_win.yml'
    elif sys.platform == 'linux': 
        return 'environment_linux.yml'
    elif sys.platform == 'darwin': 
        return 'environment_macOS.yml'
    else:
        raise OSError('OS not supported')

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
        miniconda_installer_path = os.path.abspath(
            os.path.join(miniconda_dir, '..', 'miniconda_installer.exe'))
        with open(miniconda_installer_path, 'wb') as f:
            f.write(r.content)
        logger.info('Finished downloading the Miniconda installer')
        logger.info('Installing Miniconda, this might take some time')
        run_command(
            f'{miniconda_installer_path} /InstallationType=JustMe '
            f'/RegisterPython=0 /AddToPath=0 /S /D={miniconda_dir}')
        logger.info('Finished installing Minicoda')
        os.remove(miniconda_installer_path)
    else:
        miniconda_installer_path = os.path.abspath(
            os.path.join(miniconda_dir, '..', 'miniconda_installer.sh'))
        with open(miniconda_installer_path, 'wb') as f:
            f.write(r.content)
        logger.info('Finished downloading the Miniconda installer')
        # Run the instaler
        run_command(
            f'bash {miniconda_installer_path} '
            f'-b -f -p {miniconda_dir}')
        logger.info('Finished installing Minicoda')
        os.remove(miniconda_installer_path)

def _install_env_and_simnibs(version_url, conda_executable, prefix):
    ''' Install the environment and SimNIBS
    '''
    logger.info('Installing the environment and SimNIBS')
    logger.debug(f'Download URL: {version_url}')
    logger.debug(f'Conda executable: {conda_executable}')
    activate_executable = os.path.join(os.path.dirname(conda_executable), 'activate')
    env_file = os.path.join(prefix, _env_file())
    if sys.platform == 'win32':
        run_command(
            f'call {activate_executable} && '
            f'conda update -y conda && '
            f'conda env update -f {env_file}'
        )
        run_command(
            f'call {activate_executable} simnibs_env && '
            f'pip install --upgrade -f {version_url} simnibs'
        )
    else:
        # I use "." instead of source as it is executed in an sh shell
        run_command(
            f'. {activate_executable} && '
            f'conda update -y conda && '
            f'conda env update -f {env_file}'
        )
        pip_executable = os.path.join(
            os.path.dirname(conda_executable),
            '..', 'envs', 'simnibs_env', 'bin', 'pip')
        run_command(
            f'{pip_executable} install --upgrade -f {version_url} simnibs'
        )


def _run_postinstall(conda_executable, prefix, silent):
    ''' Run SimNIBS postinstall '''
    logger.info('Running SimNIBS postinstall script')
    activate_executable = os.path.join(os.path.dirname(conda_executable), 'activate')
    logger.debug(f'activate executable: {activate_executable}')
    logger.debug(f'target dir: {prefix}') 
    # We write a shell script and execute it due to the activate calls
    if silent:
        extra_args = '-s -f'
    else:
        extra_args = ''
    if sys.platform == 'win32':
        run_command(
            f'call {activate_executable} simnibs_env && '
            f'postinstall_simnibs {extra_args} -d {prefix} --copy-matlab --setup-links'
        )
    else:
        postinstall_executable = os.path.join(
            os.path.dirname(conda_executable),
            '..', 'envs', 'simnibs_env', 'bin', 'postinstall_simnibs')
        run_command(
            f'{postinstall_executable} {extra_args} -d {prefix} '
            '--copy-matlab --setup-links'
        )


def run_command(command, log_level=logging.INFO):
    """ Run a command and logs it
    """
    logger.log(log_level, f'Execute: {command}')

    command_line_process = subprocess.Popen(
        command, shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        env=ENV
    )
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
        raise OSError(f'Error executing command: {command}')



def run_install(prefix, simnibs_version, pre_release, silent):
    ''' Main function for installation
    '''
    # Make the install directory
    if not os.path.isdir(prefix):
        os.makedirs(prefix)

    # Add a logger
    fh = logging.FileHandler(os.path.join(prefix, 'simnibs_install_log.txt'), mode='w')
    formatter = logging.Formatter(
        '[ %(name)s - %(asctime)s ]%(levelname)s: %(message)s')
    fh.setFormatter(formatter)
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)

    # Check the currently avaliable versisons
    avaliable_versions = _get_versions(pre_release)
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
    if os.path.isfile(_simnibs_exe(prefix)):
        logger.info('SimNIBS installation detected! Updating it')
        curr_version = _get_current_version(prefix)
        try:
            curr_idx = avaliable_versions[curr_version]
        except KeyError:
            curr_idx = len(avaliable_versions) + 1
            logger.info('Could not determine the current SimNIBS version')
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


    logger.info(f'Installing SimNBIS to: {prefix}')
    # Check is Miniconda is alteady present
    miniconda_dir = os.path.join(prefix, 'miniconda3')
    if sys.platform == 'win32':
        conda_executable = os.path.join(miniconda_dir, 'Scripts', 'conda.exe')
    else:
        conda_executable = os.path.join(miniconda_dir, 'bin', 'conda')

    if os.path.isfile(conda_executable):
        logger.info('Miniconda installation detected, skipping install step')
    else:
        _download_and_install_miniconda(miniconda_dir)
    # Install SimNIBS
    url = _download_env_docs(requested_version, prefix, pre_release)
    _install_env_and_simnibs(url, conda_executable, prefix)
    _run_postinstall(conda_executable, prefix, silent)
    # Move the installer as 'update_simnibs'
    target_name = os.path.join(prefix, 'bin', 'update_simnibs' + os.path.splitext(FILENAME)[1])
    if not os.path.isfile(target_name):
        shutil.copy(FILENAME, target_name)
    elif not os.path.samefile(FILENAME, target_name):
        shutil.copy(FILENAME, target_name)

    logger.info('SimNIBS successfuly installed')


class InstallGUI(QtWidgets.QWizard):
    ''' Installation wizard '''
    def __init__(self,
                 prefix,
                 simnibs_version='latest',
                 pre_release=False):
        super().__init__()
        self.prefix = prefix
        self.simnibs_version = simnibs_version
        self.pre_release = pre_release

        # Button layout without the back button

        buttons_layout = []
        buttons_layout.append(QtWidgets.QWizard.Stretch )
        buttons_layout.append(QtWidgets.QWizard.NextButton )
        buttons_layout.append(QtWidgets.QWizard.FinishButton)
        buttons_layout.append(QtWidgets.QWizard.CancelButton )
        self.setButtonLayout(buttons_layout)

        self.button(QtWidgets.QWizard.CancelButton).disconnect()
        self.button(QtWidgets.QWizard.CancelButton).clicked.connect(self.cancel)
        # Add the pages
        self.addPage(self.options_page())
        self.addPage(self.install_page())
        self.setWindowTitle('SimNIBS Installer')
        try:
            curdir = sys._MEIPASS
        except:
            curdir = '.'
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(curdir, 'gui_icon.ico')))

    def cancel(self):
        answ = QtWidgets.QMessageBox.question(
            self, 'SimNIBS installation',
            'Are you sure you want to cancel the installation?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No)
        if answ == QtWidgets.QMessageBox.Yes:
            self.reject()

    def options_page(self):
        ''' First page, where options are set '''
        options_page = QtWidgets.QWizardPage()
        options_page.setTitle('Installation Options')
        options_page.setSubTitle(
            'The installer will donwload and install SimNIBS 3 and its requiremets.\n'
            'The final installation requires about 3 GB of space')
        layout = QtWidgets.QGridLayout()

        layout.addWidget(QtWidgets.QLabel('Install Directory:'), 0, 0)
        self.prefix_line_edit = QtWidgets.QLineEdit()
        if self.prefix is not None:
            self.prefix_line_edit.setText(self.prefix)
            self.prefix_line_edit.textChanged.connect(self.set_prefix)
        layout.addWidget(self.prefix_line_edit, 0, 1)

        select_file = QtWidgets.QPushButton('&Browse')
        select_file.clicked.connect(self.select_dir)
        layout.addWidget(select_file, 0, 2)


        layout.addWidget(QtWidgets.QLabel('Version to install:'), 1, 0)
        version_box = QtWidgets.QComboBox()
        version_box.activated.connect(self.set_simnibs_version)
        self.avaliable_versions = _get_versions(self.pre_release)
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
            'I Agree to the <a href="https://raw.githubusercontent.com/simnibs/simnibs/master/LICENSE.txt"> SimNIBS </a>'
            ' and <a href="https://docs.continuum.io/anaconda/eula"> Miniconda </a> licenses')
        license_label.setOpenExternalLinks(True)
        layout.addWidget(license_label, 2, 1)
        license = QtWidgets.QCheckBox()
        layout.addWidget(license, 2, 2)

        options_page.registerField("license*", license)

        options_page.setLayout(layout)
        return options_page


    def set_prefix(self, new_value):
        self.prefix = new_value

    def select_dir(self):
        self.prefix = str(QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory"))
        if self.prefix:
            self.prefix_line_edit.setText(self.prefix)

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
                self.prefix, self.simnibs_version, self.pre_release)
            self.install_thread.start()
            self.install_thread.out_signal.connect(text_box.append)
            self.install_thread.final_message.connect(set_final_message)
            self.install_thread.finished.connect(install_page.completeChanged.emit)

        def set_final_message(successful, msg):
            if successful:
                QtWidgets.QMessageBox.information(
                    self, 'SimNIBS Installation', msg)
            else:
                QtWidgets.QMessageBox.critical(
                    self, 'SimNIBS Installation Error', msg)

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
@QtCore.pyqtSlot(bool, str)
class InstallerThread(QtCore.QThread):
    ''' Thread to install SimNIBS '''
    out_signal = QtCore.pyqtSignal(str)
    final_message = QtCore.pyqtSignal(bool, str)

    def __init__(self, prefix, simnibs_version, pre_release):
        QtCore.QThread.__init__(self)
        self.prefix = prefix
        self.simnibs_version = simnibs_version
        self.pre_release = pre_release

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
            run_install(self.prefix, self.simnibs_version, self.pre_release, False)
        except Exception as e:
            # The message box bellow is causing segmentation faults
            #QtWidgets.QMessageBox.critical(self.parent, 'Error', str(e))
            logger.critical(str(e))
            self.final_message.emit(False, str(e))
            raise e
        else:
            self.final_message.emit(True, 'Installation Successeful!')
        finally:
            logger.removeHandler(w2b_handler)

def start_gui(prefix, simnibs_version, pre_release):
    app = QtWidgets.QApplication(sys.argv)
    ex = InstallGUI(prefix, simnibs_version, pre_release)
    ex.show()
    response = app.exec_()
    sys.exit(response)


def _get_default_dir():
    # Detects is is an update proceture
    updir = os.path.abspath(
        os.path.join(
            os.path.dirname(FILENAME), '..'))
    if os.path.isfile(_simnibs_exe(updir)):
        return os.path.abspath(updir)
    if sys.platform == 'win32':
        return os.path.join(os.environ['LOCALAPPDATA'], 'SimNIBS')
    elif sys.platform == 'linux':
       return os.path.join(os.environ['HOME'], 'SimNIBS')
    elif sys.platform == 'darwin':
       return os.path.join(os.environ['HOME'], 'Applications', 'SimNIBS.app')
    else:
        raise OSError('OS not supported')


def main():
    parser = argparse.ArgumentParser(prog="install_simnibs",
                                     description="Installs or updates SimNIBS")
    parser.add_argument('-s', '--silent', action='store_true',
                        help="Run installation in silent mode (no GUI). "
                             "Will automatically accept licences and overwrite any "
                             "existing SimNIBS installation")
    parser.add_argument('-p', '--prefix', required=False,
                        help="Directory where to install SimNIBS",
                        default=_get_default_dir())
    parser.add_argument("-v", '--simnibs_version', required=False,
                        default="latest",
                        help="Version of SimNIBS to install."
                             " Default: latest version")
    parser.add_argument("--pre-release", action='store_true',
                        help= "Also list pre-release versions")
    parser.add_argument('--version', action='version', version=__version__)
    args = parser.parse_args(sys.argv[1:])
    if args.silent:
        run_install(args.prefix, args.simnibs_version, args.pre_release, True)
    else:
        start_gui(args.prefix, args.simnibs_version, args.pre_release)

# First scans the current directory for a SimNIBS install
# Then proposes a new directory

if __name__ == '__main__':
    main()
