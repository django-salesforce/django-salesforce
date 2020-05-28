(internal Wiki for project developers)

# django-salesforce Release Process

This process is largely handled by @philchristensen, who holds the credentials for the following:

* **PyPI**: pchriste
* **Salesforce**: djangosalesforce@gmail.com.dev
* **GMail**: djangosalesforce@gmail.com

It's worth noting that Phil should make sure that @hynekcer has these credentials as well. Perhaps after confirming this info with the next release.

## Testing steps
The [Travis test configuration](django-salesforce/.travis.yml) relies on [encrypted environment variables](https://docs.travis-ci.com/user/environment-variables/#defining-encrypted-variables-in-travisyml) that can only be decrypted from the official django-salesforce travis account (accessible via GitHub authentication to Owners of the django-salesforce project). To run the tests successfully, just ensure new PR submissions are pushed as branches using the first part of the command-line instructions:

    git checkout -b hynekcer-django-2.2alpha origin/master
    git pull https://github.com/hynekcer/django-salesforce hynekcer-django-2.2alpha
    git push -u origin hynekcer-django-2.2alpha


## Release steps
1. Add semantic version tag (`vX.Y.Z`) to final commit.
2. Create draft GitHub release for the new tag.
3. Upload release to PyPI
4. (optional) Upload generated *.whl files to draft release
5. Add PyPI release URL to draft release
6. Publish release

## Testing PRs
1. Follow the "command-line instructions" in the PR
2. Push the new branch up to the origin