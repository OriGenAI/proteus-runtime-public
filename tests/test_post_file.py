from pytest_bdd import scenario, given, when, then
from proteus import api


@scenario("features/post_file.feature", "Post a file")
def test_post_file(session, mocked_api_post, access_token_mock):
    "Post a file"


@given("an url", target_fixture="url")
def url():
    return "post-url"


@given("a path", target_fixture="filepath")
def filepath():
    return "tests"


@given("file content", target_fixture="content")
def content():
    return None


@when("I post a file", target_fixture="response")
def post_file(url, filepath, content):
    return api.post_file(url, filepath, content)


@then("the post file mock has been called")
def posted_file(mocked_api_post, response):
    assert response.status_code == 200
    assert mocked_api_post.called
