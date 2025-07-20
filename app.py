import pandas as pd

def format_valor_milhoes(valor):
    """Formata valor em milhões com 1 casa decimal (10,2M)"""
    if pd.isna(valor) or valor == 0:
        return "0,0M"
    
    # Sempre divide por 1 milhão (assumindo que o valor vem em unidades)
    valor_mm = valor / 1_000_000
    
    return f"{valor_mm:,.1f}M".replace(',', 'X').replace('.', ',').replace('X', '.')

# Testes
test_values = [176200000, 4785800000, 1000000, 500000]

print("Teste da função format_valor_milhoes:")
for val in test_values:
    formatted = format_valor_milhoes(val)
    print(f"{val:,.0f} -> {formatted}")

# Simular cálculo de métricas
print("\nSimulando cálculo como no Streamlit:")
total_valor_bruto = 176200000  # Valor bruto em reais
print(f"Valor bruto: {total_valor_bruto:,.0f}")
print(f"Formatado: {format_valor_milhoes(total_valor_bruto)}")
