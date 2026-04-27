import matplotlib.pyplot as plt
import pandas as pd
import io

def generate_expense_pie_chart(transactions):
    if not transactions:
        return None

    df = pd.DataFrame(transactions)
    expenses = df[df['type'] == 'expense']
    
    if expenses.empty:
        return None

    category_totals = expenses.groupby('category')['amount'].sum()

    plt.figure(figsize=(10, 6))
    category_totals.plot(kind='pie', autopct='%1.1f%%', startangle=140)
    plt.title('Distribuição de Gastos por Categoria')
    plt.ylabel('')
    
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png')
    img_buf.seek(0)
    plt.close()
    
    return img_buf
