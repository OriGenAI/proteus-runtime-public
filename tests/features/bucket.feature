Feature: Download bucket
    Scenario: Download bucket
        Given a bucket uuid
        And a target folder
        And an api mock
        When I download
        Then there are logged messages
        And the file is downloaded
