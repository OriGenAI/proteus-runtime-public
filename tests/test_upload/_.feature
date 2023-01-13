Feature: Upload files
  Background:
    Given a runtime instance
    Given a random file
    And a random url to upload files

  Scenario: when presigned uploads are enabled in backend
    Given a backend that does support preprocessing
    When a file is uploaded via .api.post_file
    Then the file is uploaded directly to AZ blob storage
    Then the system notifies the backend that the file is ready after the upload

  Scenario: when presigned uploads are not enabled in backend
    Given a backend that does not support preprocessing
    When a file is uploaded via .api.post_file
    Then the system tries first to obtain a presigned url, and when backend denies that request, tries again a direct upload
