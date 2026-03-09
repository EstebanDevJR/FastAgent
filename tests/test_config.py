from fastagent.utils.config import slugify_project_name


def test_slugify_project_name() -> None:
    assert slugify_project_name("  My Fancy_Project!!!  ") == "my-fancy-project"
    assert slugify_project_name("___") == ""