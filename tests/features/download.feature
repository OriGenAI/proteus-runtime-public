Feature: Download data
    Background:
        Given an url
    Scenario: Download data
        When I download a file with stream=<stream> and timeout=<timeout>
        Then the file is downloaded with stream=<stream> and timeout=<timeout>
        Examples:
            | stream  | timeout |
            |   False |    None |
            |   False |      60 |
            |    True |    None |
            |    True |      60 |
    Scenario: Download and store data
        Given a path
        And a file name
        When I store a file with stream=<stream> and timeout=<timeout>
        Then the file is stored with stream=<stream> and timeout=<timeout>
        Examples:
            | stream  | timeout |
            |   False |    None |
            |   False |      60 |
            |    True |    None |
            |    True |      60 |