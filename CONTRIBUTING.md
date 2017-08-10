# Contributing

_(Most of this is copied from @thoughtbot's [factory_girl_rails project].)_

Pull requests are highly encouraged from everyone. By participating in this project, you
agree to abide by the [code of conduct].

[factory_girl_rails project]: https://github.com/thoughtbot/factory_girl_rails/blob/master/CONTRIBUTING.md
[code of conduct]: https://github.com/django-salesforce/django-salesforce/blob/master/CODE_OF_CONDUCT.md

Fork, then clone the repo:

    git clone git@github.com:your-username/django-salesforce.git

Using [virtualenvwrapper] create a new env and install django-salesforce:

    mkvirtualenv django-salesforce
    pip install --editable .

Make your change. Add tests for your change. Make the tests pass:

    pip install tox
    tox -r

Push to your fork and [submit a pull request][pr].

[virtualenvwrapper]: https://virtualenvwrapper.readthedocs.io/en/latest/
[pr]: https://github.com/django-salesforce/django-salesforce/compare/

At this point you're waiting on us. We like to at least comment on pull requests
within three business days (and, typically, one business day). We may suggest
some changes or improvements or alternatives.

Some things that will increase the chance that your pull request is accepted:

* Write tests
* Different feature submissions should be submitted in different PRs
* Rebase your branch against master before submission
* Write a [good commit message][commit]

[style]: https://github.com/thoughtbot/guides/tree/master/style
[commit]: http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html
