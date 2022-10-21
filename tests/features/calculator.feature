Feature: Calculate
    Scenario: Calculate from matrix
        Given a matrix
        When I check the following expr: <expr> with the given matrix and context: <ctx>
        Then the expression is valid
        Then the result is an array
        Examples:
            | expr    | ctx    |
            |   (1+$a)*$a  | {}    |
            |   -1+$a  | {}    |
            |   $poro+$a | {"poro":3}    |
            |   Pow($a;$poro2)  | {"poro2":3}    |
            |   Sin($a)  | {}    |
            |   If($a<0.13,0,If($a<0.2,Pow(2;3),10))  |   {}  |
            |   If($a>=29 , 1, If( $a>=15 And $a<29, 2,If( $a>=12 And $a<15, 3, If( $a>=8.8 And $a<12, 4, If( $a>=1 And $a<8.8, 5, If( $a>=0.1 And $a<1, 6, 7)))) ))  | {} | 
            |   Pow(10; ((0.778+0.626*Log($a)) - (1.205*Log($a*100))))  | {} | 
            |   Sin(((0.778+0.626*Log($a)) - (1.205*Log($a*100))))  | {} | 