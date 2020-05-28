**The empty string `''`** and the **NULL** (None in Python) are **the same in a Salesforce database text field and in SOQL**. This is very different from normal SQL used in Django filters. It has one important consequence:

<h3>Never use a negative filter .exclude() with an empty string.</h3>

e.g. **Never use `Contact.objects.exclude(first_name='')`** because the following expression is true in SOQL for all rows: `FirstName != '' OR FirstName = NULL`.

<h3>The preferred way is:</h3>

**`Contact.objects.exclude(first_name__gt='')`**

More correct variants are possible for Salesforce only, but if the code should work equally with other databases, this is preferred.

----

**Explained in detail**

It is normal that an `.exclude(field='text')` will select in Django exactly opposite rows than are selected by `.filter(field='text')`. That is including a NULL value. But because the NULL and empty string are the same then would select really all without excluding anything.

| Expression in SQL /SOQL | meaning in SQL                 | meaning in SOQL                              |
|-------------------------|--------------------------------|----------------------------------------------|
| `FirstName = 'text'`    | values 'text' exactly          | values 'text' exactly                        |
| `FirstName = ''`        | values '' exactly              | values NULL (because `''` are saved as NULL) |
| `FirstName != 'text'`   | non null values except 'text'  | values except 'text' plus NULL               |
| `FirstName != ''`       | non null values except ''      | all non-empty values                         |

 A filter with a negative Q object **`.filter(~Q(last_name=''))`** is the same as **`.exclude(last_name='')`**.

<h4> &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;
 All variants in the same column are equivalent</h4>


| positive                  | negative                                                                 |
|---------------------------|--------------------------------------------------------------------------|
|`.filter(first_name='')`   | **`.filter(first_name__gt='')`** &nbsp; this is the recommended way<br/><br/> ~~`.exclude(first_name='')`~~ this is incorrect because it selects all rows  |
|`.filter(first_name=None)` | `.exclude(first_name=None)` <br><br> `.filter(first_name__isnull=False)` |

<h3>Notes:</h3>

* This can be a problem only for char fields with **`null=True`** like `fist_name = models.CharField(null=False)`.  
  Required fields with null=False are easy because they contain only non-empty values. An interesting combination is a optional field that is written as `models.CharField(default='')`

* Fields defined as a formula are different because the formula can return a null or an empty string, but not a value that is a null and an empty string at the same time.

* More info is in an issue [Excluding Empty Strings](https://github.com/django-salesforce/django-salesforce/issues/143) - An issue that results from the leaky abstraction between Salesforce and an RDBMS.