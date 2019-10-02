#! /usr/bin/env python

import os
import sys
import subprocess
import argparse
import shutil
import logging
import re
import zipfile
import tempfile
import tarfile
import stat
import ctypes
import gzip # Needed for self-update in linux

import requests
from PyQt5 import QtCore, QtWidgets, QtGui

#REMEMBER TO UPDATE THE VERSION HERE TOGETHER WITH THE RELEASE!
__version__ = '1.2'

GH_RELEASES_URL = 'https://api.github.com/repos/simnibs/simnibs/releases'

ENV=None
if getattr( sys, 'frozen', False ):
    FILENAME = sys.executable
    # THIS LINES ARE KEY TO MAKE THE PYINSTALLER-FROZEN APP WORK ON WINDOWS
    # WE NEED TO DISABLE THE SETDLLDIRECTORYA CALL OR IT WILL AFECT ALL CHILD PROCESSES
    # https://github.com/pyinstaller/pyinstaller/issues/3795
    if sys.platform == "win32":
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
sh.setLevel(logging.INFO)
logger.addHandler(sh)
logger.setLevel(logging.DEBUG)

def log_excep(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Uncaught exception",
                 exc_info=(exc_type, exc_value, exc_traceback))
    logger.debug("Traceback",
                 exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = log_excep

def self_update(silent):
    ''' Updates the updater '''
    installer_url = 'https://api.github.com/repos/simnibs/simnibs-installer/releases'
    versions, data = _get_versions(installer_url)
    try:
        curr_idx = versions[__version__]
        latest = curr_idx == 0
    except KeyError:
        latest = True
    if latest:
        return
    else:
        update = _get_input(
            'Found a new version of the SimNIBS installer, update it?',
            silent)
    if not update:
        return

    logger.info('Updating the SimNIBS installer ...')
    if sys.platform == 'linux':
        asset_name = 'install_simnibs_linux.tar.gz'
    elif sys.platform == 'darwin':
        asset_name = 'install_simnibs_macOS.zip'
    elif sys.platform == 'win32':
        asset_name = 'install_simnibs_windows.exe'
    else:
        raise OSError('OS not supported')

    tmp_fn = os.path.join(tempfile.gettempdir(), os.path.basename(FILENAME))
    if os.path.isfile(tmp_fn):
        os.remove(tmp_fn)
    shutil.move(FILENAME, tmp_fn)
    with tempfile.TemporaryDirectory() as tmpdir:
        download_name = os.path.join(tmpdir, asset_name)
        _download_asset(installer_url, data[0], asset_name, download_name)
        if sys.platform == 'win32':
            shutil.move(download_name, FILENAME) 
        elif sys.platform == 'darwin':
            with zipfile.ZipFile(download_name) as z:
                z.extractall(tmpdir)
            shutil.move(os.path.join(tmpdir, 'install_simnibs'), FILENAME) 
        elif sys.platform == 'linux':
            with tarfile.open(download_name, 'r:gz') as t:
                t.extractall(tmpdir)
            shutil.move(os.path.join(tmpdir, 'install_simnibs', 'install_simnibs'), FILENAME) 

        if sys.platform in ['linux', 'darwin']:
            os.chmod(
                FILENAME,
                os.stat(FILENAME).st_mode |
                stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    if silent:
        logger.info('SimNIBS installer updated, please start it again')
    else:
        app = QtWidgets.QApplication(sys.argv)
        QtWidgets.QMessageBox.information(
            None, 'SimNIBS installer', 'SimNIBS installer updated, please start it again')
    try:
        os.remove(tmp_fn)
    except:
        pass
    sys.exit(0) #yes, I know...

def _get_input(message, silent):
    '''Simple function to get user input via command line or GUI '''
    if silent:
        answer = input(
            f'{message} [Y/n]')
        if answer in ['n', 'N', 'no', 'No']:
            return False
        elif answer in ['', 'y', 'Y', 'yes', 'Yes']:
            return True
        else:
            raise ValueError(f'Unrecognized answer: {answer}')
    else:
        app = QtWidgets.QApplication(sys.argv)
        answer = QtWidgets.QMessageBox.question(
            None,'SimNIBS Installer', message,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        return answer == QtWidgets.QMessageBox.Yes



def _get_versions(url, pre_release=False):
    ''' Get avaliable versions and release data'''
    response = requests.get(url)
    # Raise an exception if the API call fails.
    response.raise_for_status()
    data = response.json()
    versions = {}
    for i, d in enumerate(data):
        if d['tag_name'][0] == 'v':
            if not d['prerelease']:
                versions[d['tag_name'][1:]] = i
            if d['prerelease'] and pre_release:
                versions[d['tag_name'][1:]] = i

    return versions, data

def _simnibs_exe(prefix):
    if sys.platform == 'win32':
        return os.path.abspath(os.path.join(prefix, 'bin', 'simnibs.cmd'))
    else:
        return os.path.abspath(os.path.join(prefix, 'bin', 'simnibs'))

def _get_current_version(prefix):
    ''' determines the current SimNIBS version by looking at the simnibs executable'''
    try:
        res = subprocess.check_output(
            f'"{_simnibs_exe(prefix)}" --version',
            shell=True,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            universal_newlines=True,
            errors='replace'
        )
    except subprocess.CalledProcessError:
        return None
    return res.rstrip('\n').rstrip('\r')

def _download_asset(url, release_data, asset_name, fn):
    dl_header = {'Accept': 'application/octet-stream'}
    for asset in release_data['assets']:
        if asset['name'] == asset_name:
            r = requests.get(
                f'{url}/assets/{asset["id"]}',
                headers=dl_header, allow_redirects=True)
            r.raise_for_status()
            with open(fn, 'wb') as f:
                f.write(r.content)
            return
    logger.warn(f'Could not find the asset {asset_name}')

def _download_env_docs(version, prefix, pre_release):
    ''' Looks for a given environment file os SimNIBS in the GitHub Releases
    '''
    avaliable_versions, data = _get_versions(GH_RELEASES_URL, pre_release)
    try:
        release_data = data[avaliable_versions[version]]
    except KeyError:
        ver_string = '\n'.join(avaliable_versions.keys())
        raise ValueError(
            f'\nCould not find SimNIBS version: {version}\n'
            f'Avaliable versions are:\n{ver_string}')

    # Download the environment file
    env_file = _env_file()
    logger.info(f"Version: {release_data['tag_name'][1:]}")
    logger.info("Downloading the environment file")
    _download_asset(GH_RELEASES_URL, release_data, env_file, os.path.join(prefix, env_file))
    logger.info('Finished downloading the environment file')
    logger.info("Downloading the documentation")
    _download_asset(
        GH_RELEASES_URL, release_data, 'documentation.zip', os.path.join(prefix, 'documentation.zip'))
    logger.info('Finished downloading the documentation')
    logger.info('Extracting the documentation')
    if os.path.isdir(os.path.join(prefix, 'documentation')):
        shutil.rmtree(os.path.join(prefix, 'documentation'))
    with zipfile.ZipFile(os.path.join(prefix, 'documentation.zip')) as z:
        z.extractall(os.path.join(prefix, 'documentation'))
    os.remove(os.path.join(prefix, 'documentation.zip'))
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
            f'"{miniconda_installer_path}" /InstallationType=JustMe '
            f'/RegisterPython=0 /AddToPath=0 /S /D={miniconda_dir}')
        # The /D argument should NOT be wrapped in ""
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
            f'bash "{miniconda_installer_path}" '
            f'-b -f -p "{miniconda_dir}"')
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
            f'call "{activate_executable}" && '
            f'conda update -y conda && '
            f'conda env update -f "{env_file}"'
        )
        run_command(
            f'call "{activate_executable}" simnibs_env && '
            f'pip install --no-cache-dir --upgrade -f {version_url} simnibs'
        )
    else:
        # I use "." instead of source as it is executed in an sh shell
        run_command(
            f'. "{activate_executable}" && '
            f'conda update -y conda && '
            f'conda env update -f "{env_file}"'
        )
        pip_executable = os.path.join(
            os.path.dirname(conda_executable),
            '..', 'envs', 'simnibs_env', 'bin', 'pip')
        run_command(
            f'"{pip_executable}" install --no-cache-dir --upgrade -f {version_url} simnibs'
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
            f'call "{activate_executable}" simnibs_env && '
            f'postinstall_simnibs {extra_args} -d "{prefix}" --copy-matlab --setup-links'
        )
    else:
        postinstall_executable = os.path.join(
            os.path.dirname(conda_executable),
            '..', 'envs', 'simnibs_env', 'bin', 'postinstall_simnibs')
        run_command(
            f'"{postinstall_executable}" {extra_args} -d "{prefix}" '
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
        env=ENV, universal_newlines=True,
        errors='replace'
    )
    while command_line_process.returncode is None:
        command_line_process.poll()
        for line in command_line_process.stdout:
            line = line.rstrip('\n')
            if line != '':
                logger.log(log_level, line)

    _, stderr = command_line_process.communicate()
    stderr = stderr
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
    prefix = os.path.abspath(prefix)
    if " " in prefix:
        text = "Found spaces in the installation path!"
        if sys.platform == 'win32':
            logger.warn(text)
        else:
            raise IOError(text)

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
    avaliable_versions, _ = _get_versions(GH_RELEASES_URL, pre_release)
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

    logger.info('SimNIBS successfully installed')


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
        self.successful = False

        # Button layout without the back button

        buttons_layout = []
        buttons_layout.append(QtWidgets.QWizard.Stretch )
        buttons_layout.append(QtWidgets.QWizard.NextButton )
        buttons_layout.append(QtWidgets.QWizard.FinishButton)
        buttons_layout.append(QtWidgets.QWizard.CancelButton )
        self.setButtonLayout(buttons_layout)

        self.button(QtWidgets.QWizard.CancelButton).disconnect()
        self.button(QtWidgets.QWizard.CancelButton).clicked.connect(self.cancel)
        self.page_options = 0
        self.page_install = 1
        self.page_finish = 2
        self.page_error = 3
        self.setPage(self.page_options, self.options_page())
        self.setPage(self.page_install, self.install_page())
        self.setPage(self.page_finish, self.finish_page())
        self.setPage(self.page_error, self.error_page())
        #self.setStartID(self.Page_options)
        self.setWindowTitle(f'SimNIBS Installer {__version__}')
        try:
            curdir = sys._MEIPASS
        except:
            curdir = '.'
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(curdir, 'gui_icon.ico')))

        if sys.platform == 'darwin':
            self.setWizardStyle(QtWidgets.QWizard.MacStyle)
        else:
            self.setWizardStyle(QtWidgets.QWizard.ModernStyle)

    def nextId(self):
        if self.currentId() == self.page_install:
            if self.successful:
                return self.page_finish
            else:
                return self.page_error
        elif self.currentId() == self.page_finish:
            return -1
        elif self.currentId() == self.page_error:
            return -1
        else:
            return self.currentId() + 1

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
            'The installer will donwload and install SimNIBS and its requiremets.\n'
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
        self.avaliable_versions, _ = _get_versions(GH_RELEASES_URL, self.pre_release)
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
        self.successful = False
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
                self.successful = True
            else:
                QtWidgets.QMessageBox.critical(
                    self, 'SimNIBS Installation Error', msg)
                self.successful = False

        def install_finished():
            ''' Changes the status '''
            if self.install_thread is None:
                return False
            else:
                return self.install_thread.isFinished()

        install_page.initializePage = start_thread
        install_page.isComplete = install_finished
        

        return install_page

    def finish_page(self):
        finish_page = QtWidgets.QWizardPage()
        finish_page.setTitle('Installation Successful')

        latest_release = _get_versions(
            'https://api.github.com/repos/simnibs/example-dataset/releases')[1][0]
        example_url = None
        for asset in latest_release['assets']:
            if asset['name'] == 'simnibs_examples.zip':
                example_url = asset['browser_download_url']
        if example_url is None:
            example_url = 'https://simnibs.github.io/simnibs/build/html/dataset.html'


        layout = QtWidgets.QVBoxLayout()
        text = QtWidgets.QLabel(
            f'<font size="+1">'
            f'To learn more about SimNIBS, please'
            f'<ul>'
            f'<li> <a href="https://simnibs.github.io/simnibs"> Visit our website </a> </li>'
            f'<li> <a href="{example_url}"> Download the example dataset </a> </li>'
            f'<li> <a href="https://simnibs.github.io/simnibs/build/html/tutorial/gui.html"> Follow the tutorial </a>'
            f'</ul>'
            f'</font>'
            )
        text.setOpenExternalLinks(True)
        text.setWordWrap(True)
        layout.addWidget(text)

        finish_page.setLayout(layout)
        return finish_page

    def error_page(self):
        error_page = QtWidgets.QWizardPage()
        error_page.setTitle('There was an error installing SimNIBS')
        def make_layout():
            layout = QtWidgets.QVBoxLayout()
            text = QtWidgets.QLabel(
                'Please visit <a href="http://www.simnibs.org"> www.simnibs.org </a> '
                'for troubleshooting information')
            text.setOpenExternalLinks(True)
            text.setWordWrap(True)
            layout.addWidget(text)
            layout.addWidget(QtWidgets.QLabel(
                'If the error persists, please send the file:'))
            layout.addWidget(QtWidgets.QLabel(
                f'{os.path.join(self.prefix, "simnibs_install_log.txt")}'))
            layout.addWidget(QtWidgets.QLabel(
                'to support@simnibs.org'))
            error_page.setLayout(layout)

        error_page.initializePage = make_layout
        return error_page




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
       return os.path.join(os.environ['HOME'], 'Applications', 'SimNIBS')
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
    self_update(args.silent)
    if args.silent:
        run_install(args.prefix, args.simnibs_version, args.pre_release, True)
    else:
        start_gui(args.prefix, args.simnibs_version, args.pre_release)

# First scans the current directory for a SimNIBS install
# Then proposes a new directory

if __name__ == '__main__':
    main()
