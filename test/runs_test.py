"""
Module for testing the Terraform Cloud API Endpoint: Runs.
"""

import time

from .base import TestTFCBaseTestCase


class TestTFCRuns(TestTFCBaseTestCase):
    """
    Class for testing the Terraform Cloud API Endpoint: Runs.
    """

    _unittest_name = "runs"
    _endpoint_being_tested = "runs"

    def setUp(self):
        # Create an OAuth client for the test and extract it's the token ID
        # Store the OAuth client ID to remove it at the end.
        oauth_client = self._api.oauth_clients.create(self._get_oauth_client_create_payload())
        self._oauth_client_id = oauth_client["data"]["id"]
        oauth_token_id = oauth_client["data"]["relationships"]["oauth-tokens"]["data"][0]["id"]

        # Create a workspace using that token ID, save the workspace ID
        _ws_payload = self._get_ws_with_vcs_create_payload(oauth_token_id)
        workspace = self._api.workspaces.create(_ws_payload)["data"]
        self._ws_id = workspace["id"]

        # Configure the required variables on the workspace
        variable_payloads = [
            self._get_variable_create_payload(
                "email", self._test_email, self._ws_id),
            self._get_variable_create_payload(
                "org_name", "terrasnek_unittest", self._ws_id),
            self._get_variable_create_payload(
                "TFE_TOKEN", self._test_api_token, self._ws_id, category="env", sensitive=True)
        ]
        for payload in variable_payloads:
            self._api.variables.create(payload)

        # Sleep for 1 second to give the WS time to create
        time.sleep(1)

    def tearDown(self):
        self._api.workspaces.destroy(workspace_id=self._ws_id)
        self._api.oauth_clients.destroy(self._oauth_client_id)

    def test_run_and_apply(self):
        """
        Test the Runs API endpoints: ``create``, ``show``, ``apply``.
        """
        # Create a run
        create_run_payload = self._get_run_create_payload(self._ws_id)
        run = self._api.runs.create(create_run_payload)["data"]
        run_id = run["id"]

        # Wait for it to plan
        created_run = self._api.runs.show(run_id)["data"]
        while not created_run["attributes"]["actions"]["is-confirmable"]:
            self._logger.debug("Waiting on plan to execute...")
            time.sleep(1)
            created_run = self._api.runs.show(run_id)["data"]
        self._logger.debug("Plan successful.")

        self.assertEqual(created_run["relationships"]["workspace"]["data"]["id"],
                         create_run_payload["data"]["relationships"]["workspace"]["data"]["id"])
        self.assertTrue(created_run["attributes"]["actions"]["is-confirmable"], True)
        self.assertRaises(
            KeyError, lambda: created_run["attributes"]["status-timestamps"]["applying-at"])

        # List the runs, using the correct parameters, confirm it has been created
        all_runs = self._api.runs.list(self._ws_id, page=0, page_size=50)["data"]
        found_run = False
        for run in all_runs:
            if run["id"] == run_id:
                found_run = True
                break
        self.assertTrue(found_run)

        # Apply the plan
        self._api.runs.apply(run_id)

        # Wait for the plan to apply, then confirm the apply took place
        status_timestamps = self._api.runs.show(run_id)["data"]["attributes"]["status-timestamps"]
        while "applying-at" not in status_timestamps:
            time.sleep(1)
            status_timestamps = \
                self._api.runs.show(run_id)["data"]["attributes"]["status-timestamps"]
        self.assertIsNotNone(status_timestamps["applying-at"])

    def test_run_and_discard(self):
        """
        Test the Runs API endpoint: ``discard``.
        """

        # Give the worksapce a little time to create
        time.sleep(1)

        # Create a run
        create_run_payload = self._get_run_create_payload(self._ws_id)
        run = self._api.runs.create(create_run_payload)["data"]
        run_id = run["id"]

        created_run = self._api.runs.show(run_id)["data"]
        self.assertRaises(
            KeyError, lambda: created_run["attributes"]["status-timestamps"]["discarded-at"])

        while not created_run["attributes"]["actions"]["is-confirmable"]:
            self._logger.debug("Waiting on plan to execute...")
            time.sleep(1)
            created_run = self._api.runs.show(run_id)["data"]
        self._logger.debug("Plan successful.")

        # Discard the run
        self._api.runs.discard(run_id)
        status_timestamps = self._api.runs.show(run_id)["data"]["attributes"]["status-timestamps"]
        while "discarded-at" not in status_timestamps:
            time.sleep(1)
            status_timestamps = \
                self._api.runs.show(run_id)["data"]["attributes"]["status-timestamps"]
        self.assertIsNotNone(status_timestamps["discarded-at"])

    def test_run_and_cancel(self):
        """
        Test the Runs API endpoint: cancel.
        """
        # Create a run
        create_run_payload = self._get_run_create_payload(self._ws_id)
        run = self._api.runs.create(create_run_payload)["data"]
        run_id = run["id"]

        # Show the created run, make sure it hasn't yet been cancelled
        created_run = self._api.runs.show(run_id)["data"]
        self.assertIsNone(created_run["attributes"]["canceled-at"])

        # Wait for it to plan
        self._logger.debug("Sleeping while plan half-executes...")
        time.sleep(1)
        self._logger.debug("Done sleeping.")

        # Cancel the run, confirm it has been cancelled
        self._api.runs.cancel(run_id)
        status_timestamps = self._api.runs.show(run_id)["data"]["attributes"]["status-timestamps"]
        while "force-canceled-at" not in status_timestamps:
            time.sleep(1)
            status_timestamps = \
                self._api.runs.show(run_id)["data"]["attributes"]["status-timestamps"]
        self.assertIsNotNone(status_timestamps["force-canceled-at"])
