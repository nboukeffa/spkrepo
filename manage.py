# -*- coding: utf-8 -*-
import datetime
import json
import os
import re
import shutil
from unittest import TextTestRunner

from flask import current_app
from flask_migrate import MigrateCommand
from flask_script import Manager, Option
from flask_security.script import (
    ActivateUserCommand,
    AddRoleCommand,
    CreateRoleCommand,
    CreateUserCommand,
    DeactivateUserCommand,
    RemoveRoleCommand,
    commit,
)
from flask_security.utils import encrypt_password
from spkrepo import create_app
from spkrepo.ext import db
from spkrepo.models import Architecture, Package, user_datastore

manager = Manager(create_app)
manager.add_option("-c", "--config", dest="config", required=False)

# Migrate commands
manager.add_command("db", MigrateCommand)


def date_handler(obj):
    return obj.isoformat() if hasattr(obj, "isoformat") else obj


def pprint(obj):
    print(json.dumps(obj, default=date_handler, sort_keys=True, indent=4))


# User commands
class CreateSpkrepoUserCommand(CreateUserCommand):
    """Create a user"""

    option_list = (
        Option("-u", "--username", dest="username", default=None),
        Option("-e", "--email", dest="email", default=None),
        Option("-p", "--password", dest="password", default=None),
        Option("-a", "--active", dest="active", default=""),
        Option("-c", "--confirmed", dest="confirmed", default=""),
    )

    @commit
    def run(self, **kwargs):
        # handle confirmed
        if re.sub(r"\s", "", str(kwargs.pop("confirmed"))).lower() in [
            "",
            "y",
            "yes",
            "1",
            "active",
        ]:
            kwargs["confirmed_at"] = datetime.datetime.now()

        # sanitize active input
        ai = re.sub(r"\s", "", str(kwargs["active"]))
        kwargs["active"] = ai.lower() in ["", "y", "yes", "1", "active"]

        from flask_security.forms import ConfirmRegisterForm
        from werkzeug.datastructures import MultiDict

        form = ConfirmRegisterForm(MultiDict(kwargs), csrf_enabled=False)

        if form.validate():
            kwargs["password"] = encrypt_password(kwargs["password"])
            user_datastore.create_user(**kwargs)
            print("User created successfully.")
            kwargs["password"] = "****"
            pprint(kwargs)
        else:
            print("Error creating user")
            pprint(form.errors)


UserCommand = Manager(usage="Perform user actions")
UserCommand.add_command("create", CreateSpkrepoUserCommand)
UserCommand.add_command("activate", ActivateUserCommand)
UserCommand.add_command("deactivate", DeactivateUserCommand)
UserCommand.add_command("create_role", CreateRoleCommand)
UserCommand.add_command("remove_role", RemoveRoleCommand)
UserCommand.add_command("add_role", AddRoleCommand)
manager.add_command("user", UserCommand)


@MigrateCommand.command
def drop():
    """Drop database"""
    db.drop_all()


@MigrateCommand.command
def create():
    """Create Database"""
    from spkrepo.tests.common import populate_db

    db.create_all()
    populate_db()
    db.session.commit()


@MigrateCommand.command
def populate():
    """Populate the database with some packages"""
    from spkrepo.tests.common import BuildFactory, PackageFactory, VersionFactory

    with db.session.no_autoflush:
        # nzbget
        nzbget_package = PackageFactory(name="nzbget")
        nzbget_versions = [
            VersionFactory(
                package=nzbget_package,
                upstream_version="12.0",
                version=10,
                dependencies=None,
                report_url=None,
                install_wizard=True,
                upgrade_wizard=False,
            ),
            VersionFactory(
                package=nzbget_package,
                upstream_version="13.0",
                version=11,
                dependencies=None,
                report_url=None,
                install_wizard=True,
                upgrade_wizard=False,
            ),
        ]
        nzbget_builds = []
        for version in nzbget_versions:
            builds = BuildFactory.create_batch(2, version=version, active=True)
            nzbget_builds.extend(builds)

        # sickbeard
        sickbeard_package = PackageFactory(name="sickbeard")
        sickbeard_versions = [
            VersionFactory(
                package=sickbeard_package,
                upstream_version="20140528",
                version=3,
                dependencies="git",
                service_dependencies=[],
                report_url=None,
                install_wizard=False,
                upgrade_wizard=False,
                startable=True,
            ),
            VersionFactory(
                package=sickbeard_package,
                upstream_version="20140702",
                version=4,
                dependencies="git",
                service_dependencies=[],
                report_url=None,
                install_wizard=False,
                upgrade_wizard=False,
                startable=True,
            ),
        ]
        sickbeard_builds = []
        for version in sickbeard_versions:
            sickbeard_builds.append(
                BuildFactory(
                    version=version,
                    architectures=[Architecture.find("noarch")],
                    active=True,
                )
            )

        # git
        git_package = PackageFactory(name="git")
        git_versions = [
            VersionFactory(
                package=git_package,
                upstream_version="1.8.4",
                version=3,
                dependencies=None,
                service_dependencies=[],
                report_url=None,
                install_wizard=False,
                upgrade_wizard=False,
                startable=False,
            ),
            VersionFactory(
                package=git_package,
                upstream_version="2.1.2",
                version=4,
                dependencies=None,
                service_dependencies=[],
                report_url=None,
                install_wizard=False,
                upgrade_wizard=False,
                startable=False,
            ),
        ]
        git_builds = []
        for version in git_versions:
            builds = BuildFactory.create_batch(3, version=version, active=True)
            git_builds.extend(builds)

        # bitlbee
        bitlbee_package = PackageFactory(name="bitlbee")
        bitlbee_versions = [
            VersionFactory(
                package=bitlbee_package,
                upstream_version="3.2.2",
                version=9,
                dependencies=None,
                service_dependencies=[],
                report_url=None,
                install_wizard=False,
                upgrade_wizard=False,
                startable=True,
            ),
            VersionFactory(
                package=bitlbee_package,
                upstream_version="3.2.3",
                version=10,
                dependencies=None,
                service_dependencies=[],
                report_url=None,
                install_wizard=False,
                upgrade_wizard=False,
                startable=True,
            ),
            VersionFactory(
                package=bitlbee_package,
                upstream_version="3.3.0",
                version=11,
                dependencies=None,
                service_dependencies=[],
                install_wizard=False,
                upgrade_wizard=False,
                startable=True,
            ),
        ]
        bitlbee_builds = []
        for version in bitlbee_versions:
            builds = BuildFactory.create_batch(3, version=version, active=True)
            bitlbee_builds.extend(builds)
    db.session.commit()


@MigrateCommand.command
def depopulate():
    """Depopulate database"""
    for package in Package.query.all():
        shutil.rmtree(os.path.join(current_app.config["DATA_PATH"], package.name))
        db.session.delete(package)
    db.session.commit()


@manager.command
def clean():
    """Clean data path"""
    # do not remove and recreate the path since it may be a docker volume
    for root, dirs, files in os.walk(
        os.path.join(current_app.config["DATA_PATH"]), topdown=False
    ):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))


@manager.command
def test():
    """Test spkrepo"""
    from spkrepo.tests import suite

    TextTestRunner(verbosity=2).run(suite)


if __name__ == "__main__":
    manager.run()
