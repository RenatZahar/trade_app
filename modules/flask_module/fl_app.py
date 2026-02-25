# fl_app.py

import os
import time
from config import setup_logging, BLOCKS_SQL_DATA
import os
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from plotly.offline import plot
from flask import Flask, render_template, request, flash
from pathlib import Path

logger = setup_logging(__name__)
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)



app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Необходим для flash сообщений

@app.route('/', methods=['GET', 'POST'])
def index():
    plot_div = None
    columns_info = None
    selected_column1 = None  
    selected_column2 = None 
    
    if request.method == 'POST':
        file_path = request.form['file_path']
        try:
            if Path(file_path).exists() and file_path.endswith('.parquet'):
                df = pd.read_parquet(file_path)
                df.reset_index(inplace=True)
                columns_info = {
                    'names': list(df.columns),
                    'dtypes': [str(dtype) for dtype in df.dtypes],
                    'non_null_counts': [str(count) for count in df.count()],
                    'sample_values': [str(df[col].iloc[0]) if not df[col].empty else 'N/A' 
                                    for col in df.columns]
                }
                
                selected_column1 = request.form.get('selected_column1')
                selected_column2 = request.form.get('selected_column2')
                
                if (selected_column1 and selected_column1 in df.columns) or (selected_column2 and selected_column2 in df.columns):
                    # Создаём фигуру с дополнительной осью Y
                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    
                    # Данные для первого столбца (например, Price)
                    if selected_column1 and selected_column1 in df.columns:
                        y_data1 = df[selected_column1]
                        if not y_data1.isnull().all():
                            hover_text1 = [
                                f'Индекс: {idx}<br>{selected_column1}: {val:.2f}'
                                for idx, val in enumerate(y_data1)
                            ]
                            fig.add_trace(
                                go.Scatter(
                                    x=list(range(len(df))),
                                    y=y_data1.tolist(),
                                    mode='lines',
                                    name=selected_column1,
                                    text=hover_text1,
                                    hoverinfo='text+name',
                                    line=dict(width=1, color='blue')
                                ),
                                secondary_y=False  # Левый Y-акс
                            )
                    
                    # Данные для второго столбца (например, Action)
                    if selected_column2 and selected_column2 in df.columns:
                        y_data2 = df[selected_column2]
                        if not y_data2.isnull().all():
                            hover_text2 = [
                                f'Индекс: {idx}<br>{selected_column2}: {val:.2f}'
                                for idx, val in enumerate(y_data2)
                            ]
                            fig.add_trace(
                                go.Scatter(
                                    x=list(range(len(df))),
                                    y=y_data2.tolist(),
                                    mode='lines',
                                    name=selected_column2,
                                    text=hover_text2,
                                    hoverinfo='text+name',
                                    line=dict(width=1, color='red')
                                ),
                                secondary_y=True  # Правый Y-акс
                            )

                    # Настройка осей: левой и правой
                    # Можно вычислить минимумы/максимумы для каждой оси, если хотите задать диапазоны вручную
                    fig.update_layout(
                        title='График выбранных столбцов (две оси Y)',
                        xaxis_title='Номер записи',
                        hovermode='x unified',
                        height=700,
                        showlegend=True
                    )

                    # Подписи осей
                    fig.update_yaxes(title_text=selected_column1, secondary_y=False)
                    fig.update_yaxes(title_text=selected_column2, secondary_y=True)

                    # Если хотите автоматически подстроить диапазон, Plotly это сделает сам.
                    # Но при необходимости можно задать вручную:
                    #
                    # fig.update_yaxes(range=[min_val1, max_val1], secondary_y=False)
                    # fig.update_yaxes(range=[min_val2, max_val2], secondary_y=True)

                    plot_div = plot(fig, output_type='div', include_plotlyjs=False)
                
            else:
                flash('Пожалуйста, укажите правильный путь к файлу .parquet')
        except Exception as e:
            flash(f'Ошибка при чтении файла: {str(e)}')
    
    return render_template('plotly_graph.html', 
                        plot_div=plot_div, 
                        columns_info=columns_info,
                        selected_column1=selected_column1,
                        selected_column2=selected_column2)


if __name__ == '__main__':
    print('flask app.secret_key = your_secret_key  # Необходим для flash сообщений')
