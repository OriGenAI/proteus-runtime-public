Feature: Generate a report
    Scenario: Send a report
        Given a reporting instance
        When sending a report with message: reporting status
        Then the mocked api is called once
        And the message is in the standard output
    
    Scenario: Send a report without api instance
        Given a reporting instance without api reference
        When sending a report with message: reporting status
        Then the mocked api is not called
        And the message is in the standard output

    Scenario: Log info message
        When I log the messsage: logging some info
        Then I get a stdout message with: logging some info

    Scenario: Log error message
        When I log the error messsage: logging an error
        Then I get a stderr message with: logging an error
