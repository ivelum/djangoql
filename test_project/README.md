# DjangoQL test project
This project created for testing and development purposes.


## Prerequisites
1. You have forked and cloned project - `git clone git@github.com:ivelum/djangoql.git`
2. You have installed and activated [virtualenv](https://virtualenv.pypa.io/en/stable/)


## Initial setup
* Add root directory of project (`/djangoql`) to `PYTHONPATH` - `export PYTHONPATH="$(PYTHONPATH):$(pwd)""`
* Install Python packages for test project - `pip install -r requirements.txt`
* Migrate - `python manage.py migrate`
* Also, test project has predefined initial set of data ([django fixture](https://docs.djangoproject.com/en/1.11/ref/django-admin/#loaddata)) and you can install it - `python manage.py loaddata core.json`
* To acces in admin panel use this credentials:
    * Username - `hello`
    * Password - `helloworld`
    
    Or
    * Username - `batman`
    * password - `hellobatman`
