# -------------------------------------------------------------------------------------------------------------------- #
# imports
# -------------------------------------------------------------------------------------------------------------------- #

import numpy as np
from datetime import datetime


# -------------------------------------------------------------------------------------------------------------------- #
# support functions
# -------------------------------------------------------------------------------------------------------------------- #

def setup_variables():
    print("\nsetup the basic components of a new mortgage")
    interest_rate = input("type an interest rate\t>> ")
    years = input("how many years is the loan?\t>> ")
    payments_year = input("how many payments will you make each year?\t>> ")
    principal = input("what is your principal (amount borrowed)?\t>> ")
    period = 1
    start_date = datetime.today()

    # return loan variables
    return {'interest_rate': float(interest_rate), 'years': int(years), 'payments_per_year': int(payments_year),
            'payments_remaining': int(years)*int(payments_year), 'initial_principal': float(principal),
            'principal_remaining': float(principal), 'period': period, 'interest_paid': 0, 'start_date': start_date}


def check_loan(loan):
    if len(loan) == 0:
        print("Not setup yet...\n")

    else:
        print("")
        for variable in loan:
            print(variable, "-", loan[variable])


def calculate_period(loan, period):
    """ will calculate the interest and principal payments for a selected payment period """

    # calculate the monthly payment
    monthly_payment = np.pmt(loan['interest_rate'] / loan['payments_per_year'], loan['years'] *
                             loan['payments_per_year'], loan['initial_principal'])

    # calculate the interest for a given period
    interest_payment = np.ipmt(loan['interest_rate'] / loan['payments_per_year'], period,
                               loan['years'] * loan['payments_per_year'], loan['initial_principal'])

    # calculate the principal for a give period
    principal_payment = np.ppmt(loan['interest_rate'] / loan['payments_per_year'], period, loan['years'] *
                                loan['payments_per_year'], loan['initial_principal'])

    print("\nthe monthly payment for this period is:", "$" + str(round(monthly_payment*-1, 2)))
    print("the interest payment for this period is:", "$" + str(round(interest_payment*-1, 2)))
    print("the principal payment for this period is:", "$" + str(round(principal_payment*-1, 2)))


def make_current_payment(loan, period):
    """ will subtract the period's principal payment off of the loan """
    try:
        print("\npayment", loan['period'], "with", loan['principal_remaining'], "principal remaining on the loan")

        # calculate the interest for a given period
        interest_payment = np.ipmt(loan['interest_rate'] / loan['payments_per_year'], period,
                                   loan['years'] * loan['payments_per_year'], loan['initial_principal'])

        # calculate the principal for a give period
        principal_payment = np.ppmt(loan['interest_rate'] / loan['payments_per_year'], period, loan['years'] *
                                    loan['payments_per_year'], loan['initial_principal'])

        # reset the balance on the loan and adjust the principal
        loan['principal_remaining'] = round(loan['principal_remaining'] + principal_payment, 2)
        loan['interest_paid'] = round(loan['interest_paid'] - interest_payment, 2)
        loan['payments_remaining'] -= 1
        loan['period'] += 1

        print("-------------------------------------------------------------")
        print(loan['payments_remaining'], "payments remaining on the loan")
        print("principal after payment:", loan['principal_remaining'])
        print("total interest paid:", loan['interest_paid'])

    except TypeError:
        print("invalid loan data")

    return loan


def make_principal_payment(loan):
    # Todo: make a principal payment
    """ how do you adjust the schedule after making additional payments """
    return loan


# -------------------------------------------------------------------------------------------------------------------- #
# support functions
# -------------------------------------------------------------------------------------------------------------------- #

def loan_app():
    # define global mortgage
    loan = {}

    print("\nWelcome to my amortization calculator, select a menu option to begin!!!!")

    # start running the application once a loan is passed in as a parameter
    application_is_active = True

    while application_is_active:
        print("\n1) Enter loan details\n"
              "2) Check current loan\n"
              "3) Calculate payment for a period on original loan\n"
              "4) Make the current payment period\n"
              "5) Make an additional payment against the principal\n"
              "6) Quit the program")

        selection = input("\n>> ")

        if selection == "1":
            loan = setup_variables()

        elif selection == "2":
            check_loan(loan)

        elif selection == "3":
            print("\ncurrent loan is", loan['years'], "years with", loan['payments_per_year'],
                  "payments scheduled per year for", int(loan['years']) * int(loan['payments_per_year']),
                  "payment periods")

            # select a period to check on
            period = input("what period do you want to calculate?\n>> ")
            try:
                period = int(period)
                # call function to actually calculate the mortgage payment for the period
                calculate_period(loan, period)
            except TypeError:
                print("invalid period entry")

        elif selection == "4":
            # Todo: adjust the balance when a payment is made against the principal
            loan = make_current_payment(loan, loan['period'])

        elif selection == "5":
            # Todo: adjust the payments when a period payment is made :) (balance - principal payment)
            make_current_payment(loan, loan['period'])

        elif selection == "6":
            print("\ngoodbye, have a nice day :)")
            quit()


# -------------------------------------------------------------------------------------------------------------------- #
# main
# -------------------------------------------------------------------------------------------------------------------- #

def run():
    loan_app()
