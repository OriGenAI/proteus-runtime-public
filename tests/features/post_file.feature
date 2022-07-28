Feature: Post a file
    Scenario: Post a file
        Given an url
        And a path
        And file content
        When I post a file 
        Then the post file mock has been called
